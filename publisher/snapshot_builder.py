"""Capture the enabled player build as one ZIP, streamed into bounded parts.

No second full archive is created. A callback may upload and retire each closed
part. The concatenated parts are an ordinary ZIP64 archive, compatible with the
installer's existing SHA-256 download/assembly path.
"""
from __future__ import annotations

import collections
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import zipfile

RUNTIME_FOLDERS = {'dlls','explorer++','licenses','loot','ncc','platforms',
    'plugins','pythoncore','qtqml','qtquick.2','resources','styles','stylesheets',
    'translations','tutorials'}
ROOT_FILES = {'modorganizer.exe','helper.exe','nxmhandler.exe','qtwebengineprocess.exe',
    'boost_python38-vc142-mt-x64-1_75.dll','libcrypto-1_1-x64.dll','libffi-7.dll',
    'libssl-1_1-x64.dll','python38.dll','pythoncore.zip','uibase.dll',
    'usvfs_proxy_x64.exe','usvfs_proxy_x86.exe','usvfs_x64.dll','usvfs_x86.dll',
    'splash.png','portable.txt','launch perdition sector.cmd'}
PROFILE_FILES = {'archives.txt','fallout4.ini','fallout4custom.ini','fallout4prefs.ini',
    'initweaks.ini','loadorder.txt','lockedorder.txt','modlist.txt','plugins.txt','settings.ini'}
EXCLUDED_DIRS = {'.git','__pycache__','fo4edit backups','fo4edit cache','crashdumps',
    'steamsession'}
EXCLUDED_SUFFIXES = {'.bak','.broken','.log','.fos','.f4se','.dmp','.pdb','.psd'}
EXCLUDED_NAMES = {'desktop.ini','thumbs.db'}
ZIP_DATE = (2026,11,20,0,0,0)


def include_payload(relative: str, enabled: set[str]) -> bool:
    parts = relative.replace('\\','/').split('/')
    lower = [p.lower() for p in parts]
    if any(p in EXCLUDED_DIRS for p in lower) or lower[-1] in EXCLUDED_NAMES:
        return False
    if Path(lower[-1]).suffix in EXCLUDED_SUFFIXES:
        return False
    if len(parts) == 1:
        return lower[0] in ROOT_FILES
    if lower == ['launcher','start-perdition.ps1']:
        return True
    if lower[0] in RUNTIME_FOLDERS:
        return True
    if lower[0] == 'mods' and len(parts) >= 3:
        if parts[1].lower() not in enabled or 'src' in lower:
            return False
        if lower[:3] == ['mods','f4se','f4se_0_06_23']:
            return False
        # Archived downloads and editor project artifacts are not game assets.
        return Path(lower[-1]).suffix not in {'.7z','.rar','.zip','.cpp','.hpp',
            '.sln','.vcxproj','.obj','.lib','.exp','.ilk'}
    if lower[0] == 'overwrite':
        return not any(p in {'source','backup','backups','log','logs'} for p in lower) and Path(lower[-1]).suffix != '.psc'
    return len(parts) == 3 and lower[:2] == ['profiles','fo4me'] and lower[2] in PROFILE_FILES


def enabled_mods(source: Path) -> set[str]:
    text = (source/'profiles/FO4ME/modlist.txt').read_text(encoding='utf-8-sig')
    return {line[1:].strip().lower() for line in text.splitlines() if line.startswith('+')}


def inventory(source: Path) -> list[dict]:
    source = source.resolve()
    enabled = enabled_mods(source)
    rows = []
    for directory, dirs, names in os.walk(source):
        relative = Path(directory).relative_to(source)
        if not relative.parts:
            dirs[:] = [d for d in dirs if d.lower() in RUNTIME_FOLDERS|{'mods','overwrite','profiles','launcher'}]
        elif relative.parts[0].lower() == 'mods' and len(relative.parts) == 1:
            dirs[:] = [d for d in dirs if d.lower() in enabled]
        elif relative.parts[0].lower() == 'profiles' and len(relative.parts) == 1:
            dirs[:] = [d for d in dirs if d.lower() == 'fo4me']
        dirs[:] = [d for d in dirs if d.lower() not in EXCLUDED_DIRS]
        for name in dirs:
            path = Path(directory)/name
            if path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise RuntimeError('Linked source directory: '+str(path))
        for name in names:
            path = Path(directory)/name
            rel = path.relative_to(source).as_posix()
            if not include_payload(rel,enabled):
                continue
            info = path.stat()
            if path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise RuntimeError('Linked source file: '+str(path))
            rows.append({'path':rel,'bytes':info.st_size,'mtime_ns':info.st_mtime_ns})
    rows.sort(key=lambda row:row['path'])
    names = {row['path'].lower() for row in rows}
    required = {'modorganizer.exe','splash.png','launcher/start-perdition.ps1',
        'launch perdition sector.cmd','overwrite/perdition sector world.esp',
        'profiles/fo4me/modlist.txt','profiles/fo4me/plugins.txt'}
    if required - names:
        raise RuntimeError('Required player files missing: '+str(required-names))
    return rows


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


class TailReader(io.RawIOBase):
    """Seekable view of just the ZIP tail, enough to validate all directory data."""
    def __init__(self, data: bytes, total: int):
        self.data, self.total, self.position = data, total, 0
        self.start = total-len(data)

    def seek(self, offset, whence=io.SEEK_SET):
        self.position = offset if whence == io.SEEK_SET else self.position+offset if whence == io.SEEK_CUR else self.total+offset
        return self.position

    def tell(self):
        return self.position

    def seekable(self):
        return True

    def read(self, size=-1):
        if self.position < self.start:
            raise OSError('Requested data precedes the retained ZIP directory tail')
        end = self.total if size < 0 else min(self.total,self.position+size)
        result = self.data[self.position-self.start:end-self.start]
        self.position += len(result)
        return result


class SplitSink(io.RawIOBase):
    def __init__(self, folder: Path, archive_name: str, part_bytes: int,
                 callback=None, reserve_bytes=2*1024**3):
        if not 1024 <= part_bytes < 2*1024**3:
            raise ValueError('Release part size must be between 1 KiB and 2 GiB')
        self.folder = folder.resolve()
        self.folder.mkdir(parents=True,exist_ok=True)
        self.archive_name, self.part_bytes = archive_name, part_bytes
        self.callback, self.reserve_bytes = callback, reserve_bytes
        self.total = self.written = 0
        self.parts = []
        self.stream = None
        self.overall = hashlib.sha256()
        self.tail = bytearray()
        self.tail_limit = 32*1024*1024
        self.part_hash = None

    def tell(self):
        return self.total

    def seekable(self):
        return False

    def seek(self,*args):
        raise OSError('Split ZIP is streamed, not seekable')

    def writable(self):
        return True

    def write(self,data):
        original = len(data)
        if not original:
            return 0
        self.overall.update(data)
        self.tail.extend(data)
        if len(self.tail)>self.tail_limit:
            del self.tail[:-self.tail_limit]
        view = memoryview(data)
        while view:
            if self.stream is None:
                if shutil.disk_usage(self.folder).free < self.part_bytes+self.reserve_bytes:
                    raise RuntimeError('Insufficient temporary space for the next release part')
                self.path = self.folder/(self.archive_name+f'.{len(self.parts)+1:03d}')
                if self.path.exists():
                    raise RuntimeError('An unfinished part exists; preserve it or resume with a fresh parts directory: '+str(self.path))
                self.stream = self.path.open('xb')
                self.part_hash = hashlib.sha256()
                self.written = 0
            amount = min(len(view),self.part_bytes-self.written)
            self.stream.write(view[:amount])
            self.part_hash.update(view[:amount])
            self.written += amount
            self.total += amount
            view = view[amount:]
            if self.written == self.part_bytes:
                self.finish_part()
        return original

    def flush(self):
        if self.stream is not None:
            self.stream.flush()

    def close(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None
        super().close()

    def __exit__(self, exception_type, value, traceback):
        try:
            if exception_type is None:
                self.finish_part()
        finally:
            self.close()
        return False

    def finish_part(self):
        if self.stream is None:
            return
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()
        self.stream = None
        part = {'filename':self.path.name,'bytes':self.written,'sha256':self.part_hash.hexdigest()}
        self.parts.append(part)
        if self.callback:
            self.callback(self.path,part)


def compression_for(path: Path) -> int:
    if path.suffix.lower() in {'.bk2','.xwm','.jpg','.png','.zip'}:
        return zipfile.ZIP_STORED
    if path.suffix.lower() == '.ba2':
        with path.open('rb') as stream:
            if stream.read(12)[8:12] == b'DX10':
                return zipfile.ZIP_STORED
    return zipfile.ZIP_DEFLATED


def zip_info(name: str, compression=zipfile.ZIP_DEFLATED) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo('Perdition Sector/'+name,ZIP_DATE)
    info.compress_type = compression
    info._compresslevel = 1
    info.external_attr = 0o100644 << 16
    return info


def build_snapshot(source: Path, output: Path, version: str, tag: str,
                   base_url: str, callback=None, part_bytes=1900000000,
                   expected_world_hash=None, progress=None) -> dict:
    source, output = source.resolve(), output.resolve()
    rows = inventory(source)
    world_hash = digest(source/'overwrite/Perdition Sector World.esp')
    if expected_world_hash and world_hash != expected_world_hash:
        raise RuntimeError('The live World plugin has changed since this beta was prepared')
    output.mkdir(parents=True,exist_ok=True)
    (output/'source_inventory_before.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    archive_name = 'Perdition_Payload_v'+version+'.zip'
    sink = SplitSink(output/'parts',archive_name,part_bytes,callback)
    done = 0
    with sink, zipfile.ZipFile(sink,'w',allowZip64=True) as archive:
        for index,row in enumerate(rows):
            path = source/row['path']
            before = path.stat()
            if (before.st_size,before.st_mtime_ns) != (row['bytes'],row['mtime_ns']):
                raise RuntimeError('Source changed before capture: '+row['path'])
            sha = hashlib.sha256()
            with path.open('rb') as input_stream, archive.open(zip_info(row['path'],compression_for(path)),'w',force_zip64=True) as target:
                while data := input_stream.read(1024*1024):
                    sha.update(data)
                    target.write(data)
            after = path.stat()
            if (after.st_size,after.st_mtime_ns) != (row['bytes'],row['mtime_ns']):
                raise RuntimeError('Source changed during capture: '+row['path'])
            row['sha256'] = sha.hexdigest()
            done += row['bytes']
            if progress and (index%100 == 0 or index+1 == len(rows)):
                progress({'files':index+1,'total_files':len(rows),'source_bytes':done,'archive_bytes':sink.total,'path':row['path']})
        after_rows = inventory(source)
        if [{k:v for k,v in row.items() if k!='sha256'} for row in rows] != after_rows:
            raise RuntimeError('Player build changed during capture; the draft release must not be published')
        metadata = {'product':'Perdition Sector','version':version,'tag':tag,'status':'beta',
            'runtime':'1.10.163','f4se':'0.6.23','profile':'FO4ME','file_count':len(rows),
            'installed_payload_bytes':sum(row['bytes'] for row in rows),
            'world_plugin_sha256':world_hash,
            'scope':'Enabled player build only; saves, credentials, game depots and authoring tools excluded',
            'confirmed_fixes':{'subway_poster_references':17,'subway_reentry':'User confirmed repaired'},
            'known_issues':['Grass remains unresolved','NVG precipitation remains unresolved',
                'Museum floor/precombines remain unresolved']}
        for name,data in [('snapshot.json',metadata),('inventory.json',rows)]:
            archive.writestr(zip_info('_Snapshot_Metadata/'+name),json.dumps(data,indent=2).encode('utf-8'))
    sink.finish_part()
    expected_names = {'Perdition Sector/'+row['path'] for row in rows} | {
        'Perdition Sector/_Snapshot_Metadata/snapshot.json','Perdition Sector/_Snapshot_Metadata/inventory.json'}
    with zipfile.ZipFile(TailReader(bytes(sink.tail),sink.total)) as archive:
        if set(archive.namelist()) != expected_names or len(archive.infolist()) != len(expected_names):
            raise RuntimeError('ZIP directory does not match the frozen source inventory')
        if json.loads(archive.read('Perdition Sector/_Snapshot_Metadata/snapshot.json')) != metadata:
            raise RuntimeError('Archived snapshot metadata failed validation')
        if json.loads(archive.read('Perdition Sector/_Snapshot_Metadata/inventory.json')) != rows:
            raise RuntimeError('Archived file inventory failed validation')
    parts = [dict(part,url=base_url.rstrip('/')+'/'+part['filename']) for part in sink.parts]
    manifest = {'version':version,'snapshot_tag':tag,'archive_name':archive_name,
        'archive_bytes':sink.total,'archive_sha256':sink.overall.hexdigest(),
        'installed_payload_bytes':metadata['installed_payload_bytes'],
        'world_plugin_sha256':world_hash,'parts':parts}
    for name,data in [('package_source.json',manifest),('snapshot_inventory.json',rows),('snapshot_metadata.json',metadata)]:
        (output/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
    (output/(archive_name+'.sha256.txt')).write_text(manifest['archive_sha256']+'  '+archive_name+'\n',encoding='ascii')
    return manifest

