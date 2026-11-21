import argparse
import hashlib
from pathlib import Path
import tempfile
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


if __name__=='__main__':
    unittest.main()

