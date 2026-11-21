import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from publish_beta import Publisher


class UploadTests(unittest.TestCase):
    def fixture(self,temp):
        root=Path(temp)
        args=argparse.Namespace(work=root/'work',auth_dir=root/'auth',gh=root/'gh.exe',
            repository='jjc71ps4/Perdition-Sector',tag='fixture')
        publisher=Publisher(args);publisher.release_id=1
        assets={}
        publisher.assets=lambda:assets
        def fake_gh(*args,**kwargs):
            if args[:2]==('release','upload'):
                path=Path(args[3]);data=path.read_bytes()
                assets[path.name]={'id':1,'name':path.name,'state':'uploaded','size':len(data),
                    'digest':'sha256:'+hashlib.sha256(data).hexdigest(),
                    'browser_download_url':'https://example.invalid/'+path.name}
            return None
        publisher.gh=fake_gh
        return publisher,assets

    def test_verified_uploaded_part_can_be_retired(self):
        with tempfile.TemporaryDirectory(prefix='ps_publish_test_') as temp:
            publisher,assets=self.fixture(temp)
            path=publisher.work/'parts/fixture.zip.001';path.parent.mkdir();path.write_bytes(b'part')
            publisher.upload(path,retire=True)
            self.assertFalse(path.exists())
            self.assertIn(path.name,assets)
            self.assertEqual(publisher.state['uploaded_assets'][0]['sha256'],hashlib.sha256(b'part').hexdigest())

    def test_mismatched_existing_asset_preserves_local_part(self):
        with tempfile.TemporaryDirectory(prefix='ps_publish_test_') as temp:
            publisher,assets=self.fixture(temp)
            path=publisher.work/'parts/fixture.zip.001';path.parent.mkdir();path.write_bytes(b'part')
            assets[path.name]={'state':'uploaded','size':999,'digest':'sha256:'+'0'*64}
            with self.assertRaisesRegex(RuntimeError,'different release asset'):
                publisher.upload(path,retire=True)
            self.assertTrue(path.exists())

    def test_verified_asset_does_not_allow_deleting_an_unscoped_file(self):
        with tempfile.TemporaryDirectory(prefix='ps_publish_test_') as temp:
            publisher,assets=self.fixture(temp)
            path=Path(temp)/'source-file';path.write_bytes(b'part')
            with self.assertRaisesRegex(RuntimeError,'will not be removed'):
                publisher.upload(path,retire=True)
            self.assertTrue(path.exists())

    def test_missing_digest_is_not_accepted(self):
        self.assertFalse(Publisher.matches({'state':'uploaded','size':4},
            {'bytes':4,'sha256':hashlib.sha256(b'part').hexdigest()}))


class DraftReleaseTests(unittest.TestCase):
    def publisher(self,temp,pages):
        args=argparse.Namespace(work=Path(temp)/'work',auth_dir=Path(temp)/'auth',
            gh=Path(temp)/'gh.exe',repository='jjc71ps4/Perdition-Sector',
            tag='fixture',version='fixture')
        publisher=Publisher(args)
        publisher.commit_sources=lambda message:'f'*40
        calls=[]
        def fake_gh(*arguments,**kwargs):
            calls.append(arguments)
            if arguments==('api','user','--jq','.login'):
                return SimpleNamespace(stdout='jjc71ps4\n')
            if arguments==('api','repos/jjc71ps4/Perdition-Sector'):
                return SimpleNamespace(returncode=0,stdout=json.dumps({'private':False}))
            if arguments==('api','--paginate','--slurp','repos/jjc71ps4/Perdition-Sector/releases?per_page=100'):
                return pages
            if arguments[:2]==('release','create'):
                pages.append([self.release()])
                return None
            raise AssertionError('Unexpected GitHub call: '+str(arguments))
        publisher.gh=fake_gh
        return publisher,calls

    @staticmethod
    def release(draft=True):
        return {'id':453403811,'tag_name':'fixture','draft':draft,
                'html_url':'https://github.com/jjc71ps4/Perdition-Sector/releases/tag/untagged-fixture'}

    def test_existing_draft_on_later_page_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            publisher,calls=self.publisher(temp,[[{'id':1,'tag_name':'other'}],[self.release()]])
            publisher.prepare()
            self.assertEqual(publisher.release_id,453403811)
            self.assertEqual(publisher.state['status'],'draft')
            self.assertFalse(any(call[:2]==('release','create') for call in calls))

    def test_new_draft_is_found_without_published_tag_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            publisher,calls=self.publisher(temp,[[]])
            publisher.prepare()
            self.assertEqual(publisher.release_id,453403811)
            self.assertEqual(sum(call[:2]==('release','create') for call in calls),1)

    def test_published_release_is_not_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            publisher,calls=self.publisher(temp,[[self.release(draft=False)]])
            with self.assertRaisesRegex(RuntimeError,'already public'):
                publisher.prepare()
            self.assertFalse(any(call[:2]==('release','create') for call in calls))

    def test_duplicate_drafts_are_not_selected_or_recreated(self):
        with tempfile.TemporaryDirectory() as temp:
            publisher,calls=self.publisher(temp,[[self.release(),self.release()]])
            with self.assertRaisesRegex(RuntimeError,'Multiple releases'):
                publisher.prepare()
            self.assertFalse(any(call[:2]==('release','create') for call in calls))


if __name__=='__main__':
    unittest.main()

