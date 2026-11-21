"""Small fixtures cover the actual streaming archive and exclusion behavior."""
import hashlib
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
import zipfile

from snapshot_builder import build_snapshot, digest, include_payload, inventory


class SnapshotTests(unittest.TestCase):
    def fixture(self,root):
        source = root/'source'
        files = {
            'ModOrganizer.exe':b'fixture runtime',
            'splash.png':b'fixture art',
            'Launch Perdition Sector.cmd':b'fixture launch',
            'Launcher/Start-Perdition.ps1':b'fixture splash helper',
            'profiles/FO4ME/modlist.txt':b'+Live\r\n-Disabled\r\n',
            'profiles/FO4ME/plugins.txt':b'*Live.esp\r\n*Perdition Sector World.esp',
            'mods/Live/Live.esp':b'fixture plugin',
            'mods/Live/asset.dds':random.Random(47).randbytes(120000),
            'overwrite/Perdition Sector World.esp':b'fixture World plugin',
            'overwrite/MCM/Settings/Keybinds.json':b'{"key":259}',
            'profiles/FO4ME/saves/private.fos':b'private save',
            'Development/Private/hosts.yml':b'private authentication',
            'ModOrganizer.ini':b'private Nexus settings',
            'mods/Disabled/Disabled.esp':b'disabled',
            'overwrite/FO4Edit Backups/old.esp':b'backup',
            'overwrite/FO4Edit Cache/old.cache':b'cache',
            'mods/Live/src/private.cpp':b'authoring source',
            'Launcher/launcher.log':b'launch history',
        }
        for name,data in files.items():
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        return source,files

    def test_streamed_parts_reassemble_with_crc_and_inventory(self):
        with tempfile.TemporaryDirectory(prefix='ps_snapshot_test_') as temp:
            root=Path(temp);source,files=self.fixture(root);uploaded=[]
            def upload(path,part):
                data=path.read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),part['sha256'])
                self.assertLessEqual(len(data),8192)
                uploaded.append(data)
                path.unlink()
            result=build_snapshot(source,root/'output','fixture','fixture-tag',
                'https://example.invalid/fixture',upload,part_bytes=8192,
                expected_world_hash=digest(source/'overwrite/Perdition Sector World.esp'))
            data=b''.join(uploaded)
            self.assertGreater(len(uploaded),2)
            self.assertEqual(len(data),result['archive_bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(),result['archive_sha256'])
            self.assertFalse(list((root/'output/parts').iterdir()))
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertIsNone(archive.testzip())
                rows=json.loads(archive.read('Perdition Sector/_Snapshot_Metadata/inventory.json'))
                for row in rows:
                    self.assertEqual(archive.read('Perdition Sector/'+row['path']),files[row['path']])
                    self.assertEqual(row['sha256'],hashlib.sha256(files[row['path']]).hexdigest())
                self.assertEqual(sum(row['bytes'] for row in rows),result['installed_payload_bytes'])
                self.assertNotIn('Perdition Sector/ModOrganizer.ini',archive.namelist())
                self.assertFalse(any('private.fos' in name or 'hosts.yml' in name or 'FO4Edit Backups' in name for name in archive.namelist()))

    def test_source_changes_abort_capture(self):
        with tempfile.TemporaryDirectory(prefix='ps_snapshot_test_') as temp:
            root=Path(temp);source,_=self.fixture(root)
            def changed(progress):
                (source/'mods/Live/added_during_capture.esp').write_bytes(b'new edit')
            with self.assertRaisesRegex(RuntimeError,'changed during capture'):
                build_snapshot(source,root/'output','fixture','tag','https://example.invalid',
                    part_bytes=8192,progress=changed)

    def test_world_mismatch_aborts_before_archive(self):
        with tempfile.TemporaryDirectory(prefix='ps_snapshot_test_') as temp:
            root=Path(temp);source,_=self.fixture(root)
            with self.assertRaisesRegex(RuntimeError,'World plugin has changed'):
                build_snapshot(source,root/'output','fixture','tag','https://example.invalid',
                    expected_world_hash='0'*64)
            self.assertFalse((root/'output/parts').exists())

    def test_runtime_and_privacy_rules(self):
        enabled={'live','f4se'}
        for name in ['Launcher/Start-Perdition.ps1','Launch Perdition Sector.cmd',
                     'mods/Live/Scripts/live.pex','mods/F4SE/Scripts/Game.pex',
                     'overwrite/MCM/Settings/Keybinds.json']:
            self.assertTrue(include_payload(name,enabled),name)
        for name in ['ModOrganizer.ini','CreationKit.exe','tools/FO4Edit.exe',
                     'mods/Disabled/Live.esp','mods/Live/src/code.cpp',
                     'mods/F4SE/f4se_0_06_23/header.txt','overwrite/FO4Edit Cache/file',
                     'overwrite/FO4Edit Backups/file.esp','Launcher/launcher.log',
                     'profiles/FO4ME/saves/private.fos','Development/Private/hosts.yml']:
            self.assertFalse(include_payload(name,enabled),name)


if __name__=='__main__':
    unittest.main()

