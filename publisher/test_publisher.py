import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import sys
from contextlib import redirect_stdout
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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

    def test_verified_existing_part_is_reused_without_upload(self):
        with tempfile.TemporaryDirectory() as temp:
            publisher,assets=self.fixture(temp)
            path=publisher.work/'parts/fixture.zip.001';path.parent.mkdir();path.write_bytes(b'part')
            assets[path.name]={'id':1,'state':'uploaded','size':4,
                'digest':'sha256:'+hashlib.sha256(b'part').hexdigest(),'browser_download_url':'https://example.invalid/part'}
            publisher.gh=Mock(side_effect=AssertionError('Verified parts must not be uploaded or removed'))
            publisher.upload(path,retire=True)
            self.assertFalse(path.exists())
            self.assertEqual(assets[path.name]['id'],1)

    def recovery_fixture(self,temp,failures=0,draft=True,starter=False):
        publisher,assets=self.fixture(temp)
        path=publisher.work/'parts/fixture.zip.003';path.parent.mkdir();path.write_bytes(b'part')
        if starter:
            assets[path.name]={'id':77,'name':path.name,'state':'starter','size':4,'digest':None}
        calls=[]
        uploads=0
        def gh(*args,**kwargs):
            nonlocal uploads
            calls.append(args)
            if args==('api','repos/jjc71ps4/Perdition-Sector/releases/1'):
                return {'draft':draft}
            if args[:3]==('api','--method','DELETE'):
                del assets[path.name]
                return SimpleNamespace(returncode=0)
            if args[:2]==('release','upload'):
                uploads+=1
                if uploads<=failures:
                    assets[path.name]={'id':77+uploads,'name':path.name,'state':'starter','size':4,'digest':None}
                    return subprocess.CompletedProcess(args,1,'','HTTP 502: upload interrupted')
                assets[path.name]={'id':99,'name':path.name,'state':'uploaded','size':4,
                    'digest':'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest(),
                    'browser_download_url':'https://example.invalid/part'}
                return subprocess.CompletedProcess(args,0,'','')
            raise AssertionError('Unexpected call: '+str(args))
        publisher.gh=gh
        return publisher,assets,path,calls

    def test_full_sized_starter_is_recovered_in_a_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            publisher,assets,path,calls=self.recovery_fixture(temp,starter=True)
            publisher.upload(path,retire=True)
            self.assertEqual(sum(call[:3]==('api','--method','DELETE') for call in calls),1)
            self.assertEqual(sum(call[:2]==('release','upload') for call in calls),1)
            self.assertFalse(path.exists())
            self.assertEqual(assets[path.name]['state'],'uploaded')

    @patch('publish_beta.time.sleep')
    def test_failed_starter_is_retried_and_actual_error_is_logged(self,sleep):
        with tempfile.TemporaryDirectory() as temp:
            publisher,assets,path,calls=self.recovery_fixture(temp,failures=1)
            publisher.upload(path,retire=True)
            self.assertEqual(sum(call[:2]==('release','upload') for call in calls),2)
            self.assertEqual(sum(call[:3]==('api','--method','DELETE') for call in calls),1)
            log=json.loads((publisher.work/'upload_errors.log').read_text().strip())
            self.assertIn('HTTP 502',log['error'])
            self.assertEqual(log['remote_state'],'starter')
            self.assertFalse(path.exists())

    @patch('publish_beta.time.sleep')
    def test_exhausted_retries_keep_the_complete_local_part(self,sleep):
        with tempfile.TemporaryDirectory() as temp:
            publisher,assets,path,calls=self.recovery_fixture(temp,failures=3)
            with self.assertRaisesRegex(RuntimeError,'HTTP 502'):
                publisher.upload(path,retire=True)
            self.assertEqual(sum(call[:2]==('release','upload') for call in calls),3)
            self.assertEqual(path.read_bytes(),b'part')
            self.assertEqual(len((publisher.work/'upload_errors.log').read_text().splitlines()),3)

    def test_incomplete_asset_is_never_removed_from_a_published_release(self):
        with tempfile.TemporaryDirectory() as temp:
            publisher,assets,path,calls=self.recovery_fixture(temp,starter=True,draft=False)
            with self.assertRaisesRegex(RuntimeError,'published release'):
                publisher.upload(path,retire=True)
            self.assertFalse(any(call[:3]==('api','--method','DELETE') for call in calls))
            self.assertEqual(path.read_bytes(),b'part')

    def test_starter_with_unexpected_size_or_digest_is_protected(self):
        expected={'bytes':4}
        self.assertFalse(Publisher.incomplete({'state':'starter','size':3,'digest':None},expected))
        self.assertFalse(Publisher.incomplete({'state':'starter','size':4,'digest':'sha256:known'},expected))

    @patch('publish_beta.time.sleep')
    def test_delayed_server_digest_is_checked_without_reupload(self,sleep):
        with tempfile.TemporaryDirectory() as temp:
            publisher,assets,path,calls=self.recovery_fixture(temp)
            pending={'id':1,'state':'uploaded','size':4,'digest':None}
            complete=dict(pending,digest='sha256:'+hashlib.sha256(b'part').hexdigest(),browser_download_url='https://example.invalid/part')
            publisher.assets=Mock(side_effect=[{}, {path.name:pending}, {path.name:complete}])
            publisher.upload(path,retire=True)
            self.assertEqual(sum(call[:2]==('release','upload') for call in calls),1)
            self.assertFalse(any(call[:3]==('api','--method','DELETE') for call in calls))

    def test_long_upload_prints_elapsed_status(self):
        with tempfile.TemporaryDirectory() as temp:
            publisher,assets=self.fixture(temp)
            process=Mock(returncode=0)
            process.poll.side_effect=[None,None,0]
            process.wait.side_effect=[subprocess.TimeoutExpired('fixture',10),0]
            output=io.StringIO()
            with patch('publish_beta.subprocess.Popen',return_value=process), patch('publish_beta.time.monotonic',side_effect=[0,0,10,10]), redirect_stdout(output):
                result=publisher.run_upload_command(['gh.exe','release','upload','fixture','fixture.zip.001'])
            self.assertEqual(result.returncode,0)
            self.assertIn('0m 10s elapsed',output.getvalue())
            self.assertIn('Waiting for GitHub',output.getvalue())

    def test_upload_timeout_stops_the_child_and_preserves_local_file(self):
        with tempfile.TemporaryDirectory() as temp:
            publisher,assets=self.fixture(temp)
            publisher.args.upload_timeout=0.1
            path=Path(temp)/'part';path.write_bytes(b'part')
            result=publisher.run_upload_command([sys.executable,'-c','import time; time.sleep(10)','--',str(path)])
            self.assertEqual(result.returncode,124)
            self.assertIn('timeout',result.stderr)
            self.assertEqual(path.read_bytes(),b'part')


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

