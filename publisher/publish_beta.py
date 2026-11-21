"""Publish a frozen beta through a draft GitHub Release, with bounded disk use.

Requires Python 3.11+, Git, and GitHub CLI authenticated by the project owner.
Never reads or prints a token. Git uses GitHub CLI's credential helper.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from snapshot_builder import build_snapshot, digest, inventory

REPO_ROOT = Path(__file__).resolve().parents[1]


def save_json(path: Path, value):
    temporary = path.with_name(path.name+'.new')
    temporary.write_text(json.dumps(value,indent=2),encoding='utf-8')
    temporary.replace(path)


class Publisher:
    def __init__(self,args):
        self.args = args
        self.env = dict(os.environ,GH_CONFIG_DIR=str(args.auth_dir.resolve()),GH_PROMPT_DISABLED='1')
        self.work = args.work.resolve()
        self.work.mkdir(parents=True,exist_ok=True)
        self.state_path = self.work/'publish_state.json'
        self.state = {'repository':args.repository,'tag':args.tag,'status':'preparing','uploaded_assets':[]}
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
            if (self.state['repository'],self.state['tag']) != (args.repository,args.tag):
                raise RuntimeError('Another release owns the selected staging folder')
        self.last_progress = 0

    def run(self,arguments,cwd=None,check=True):
        command = [str(x) for x in arguments]
        if command[1:3]==['release','upload']:
            result = self.run_upload_command(command,cwd)
        else:
            result = subprocess.run(command,cwd=cwd,env=self.env,
                                    text=True,encoding='utf-8',capture_output=True)
        if check and result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'Command failed')
        return result

    def run_upload_command(self,command,cwd=None):
        started = time.monotonic()
        timeout = getattr(self.args,'upload_timeout',1800)
        asset = Path(command[4]).name
        with tempfile.TemporaryFile(mode='w+',encoding='utf-8') as output, tempfile.TemporaryFile(mode='w+',encoding='utf-8') as errors:
            process = subprocess.Popen(command,cwd=cwd,env=self.env,stdout=output,stderr=errors)
            timed_out = False
            try:
                while process.poll() is None:
                    remaining = timeout-(time.monotonic()-started)
                    if remaining<=0:
                        timed_out = True
                        process.kill()
                        process.wait()
                        break
                    try:
                        process.wait(timeout=min(10,remaining))
                    except subprocess.TimeoutExpired:
                        elapsed = int(time.monotonic()-started)
                        verified = sum(item['bytes'] for item in self.state['uploaded_assets'])
                        print(f'Uploading {asset}: {elapsed//60}m {elapsed%60:02d}s elapsed; '
                              f'{verified/1e9:.2f} GB already verified. Waiting for GitHub.',flush=True)
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
            output.seek(0)
            errors.seek(0)
            stderr = errors.read()
            if timed_out:
                stderr += f'\nUpload command exceeded its {timeout}-second timeout; the local file is retained.'
            return subprocess.CompletedProcess(command,124 if timed_out else process.returncode,
                                               output.read(),stderr)

    def gh(self,*arguments,json_result=False,check=True):
        result = self.run([self.args.gh,*arguments],check=check)
        return json.loads(result.stdout) if json_result else result

    def git(self,*arguments,check=True):
        return self.run(['git',*arguments],cwd=REPO_ROOT,check=check)

    def record(self,**updates):
        self.state.update(updates,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save_json(self.state_path,self.state)

    def commit_sources(self,message):
        if not (REPO_ROOT/'.git').exists():
            self.git('init','--initial-branch=main')
        self.git('config','user.name',self.args.repository.split('/')[0])
        self.git('config','user.email','359387100+jjc71ps4@users.noreply.github.com')
        self.git('config','credential.helper','!"'+str(self.args.gh.resolve()).replace('\\','/')+'" auth git-credential')
        if self.git('remote','get-url','origin',check=False).returncode:
            self.git('remote','add','origin','https://github.com/'+self.args.repository+'.git')
        remote = self.git('remote','get-url','origin').stdout.strip()
        if remote != 'https://github.com/'+self.args.repository+'.git':
            raise RuntimeError('Local repository points to a different GitHub destination')
        self.git('add','--all')
        changed = self.git('diff','--cached','--quiet',check=False)
        if changed.returncode == 1:
            self.git('commit','-m',message)
        elif changed.returncode:
            raise RuntimeError('Cannot inspect staged source changes')
        self.git('push','--set-upstream','origin','main')
        return self.git('rev-parse','HEAD').stdout.strip()

    def find_release(self):
        # The releases/tags endpoint only finds published releases. Enumerating
        # releases also exposes drafts to their owner, including pending tags.
        pages = self.gh('api','--paginate','--slurp',
            f'repos/{self.args.repository}/releases?per_page=100',json_result=True)
        matches = [release for page in pages for release in page
                   if release['tag_name']==self.args.tag]
        if len(matches)>1:
            raise RuntimeError('Multiple releases use this tag; refusing to create or select another draft')
        return matches[0] if matches else None

    def prepare(self):
        login = self.gh('api','user','--jq','.login').stdout.strip()
        if login.lower() != self.args.repository.split('/')[0].lower():
            raise RuntimeError('GitHub CLI is signed into a different account: '+login)
        result = self.gh('api','repos/'+self.args.repository,check=False)
        if result.returncode:
            if '404' not in result.stderr:
                raise RuntimeError(result.stderr.strip())
            self.gh('repo','create',self.args.repository,'--public','--description',
                'Perdition Sector: tactical horror campaign for Fallout 4. Beta installer and release snapshots.')
        else:
            repository = json.loads(result.stdout)
            if repository['private']:
                raise RuntimeError('The selected installer is configured for public downloads; repository is private')
        commit = self.commit_sources('Prepare Perdition Sector beta snapshot distribution')
        data = self.find_release()
        if data is None:
            self.gh('release','create',self.args.tag,'--repo',self.args.repository,
                '--draft','--prerelease','--title','Perdition Sector '+self.args.version+' (Beta)',
                '--target',commit,'--notes-file',str(REPO_ROOT/'RELEASE_NOTES.md'))
            data = self.find_release()
            if data is None:
                raise RuntimeError('Draft creation returned successfully but the draft is not visible yet. Rerun to resume.')
        if not data['draft']:
            raise RuntimeError('This release is already public. Published beta assets will not be changed.')
        self.release_id = data['id']
        self.record(status='draft',release_id=data['id'],release_url=data['html_url'])
        print(json.dumps({'event':'draft_ready','repository':self.args.repository,'release_id':self.release_id}),flush=True)

    def assets(self):
        pages = self.gh('api','--paginate','--slurp',
            f'repos/{self.args.repository}/releases/{self.release_id}/assets',json_result=True)
        return {asset['name']:asset for page in pages for asset in page}

    @staticmethod
    def matches(asset, expected):
        return (asset.get('state')=='uploaded' and asset.get('size')==expected['bytes']
            and asset.get('digest')=='sha256:'+expected['sha256'])

    @staticmethod
    def incomplete(asset,expected):
        # GitHub's starter size can be the declared Content-Length, even when
        # the transfer never completed. A full-looking size is not verification.
        return (asset.get('state')=='starter' and not asset.get('digest')
                and asset.get('size') in (0,expected['bytes']))

    def remove_incomplete(self,asset,expected):
        if not self.incomplete(asset,expected):
            raise RuntimeError('Refusing to remove an asset that is not an incomplete upload')
        release = self.gh('api',f'repos/{self.args.repository}/releases/{self.release_id}',json_result=True)
        if not release.get('draft'):
            raise RuntimeError('Refusing to remove an asset from a published release')
        print(json.dumps({'event':'retry_incomplete_upload','asset':expected['filename'],
                          'asset_id':asset['id']}),flush=True)
        self.gh('api','--method','DELETE',f'repos/{self.args.repository}/releases/assets/{asset["id"]}')

    def upload(self,path: Path,expected=None,retire=False):
        expected = expected or {'filename':path.name,'bytes':path.stat().st_size,'sha256':digest(path)}
        remote = self.assets().get(path.name)
        if not remote or not self.matches(remote,expected):
            for attempt in range(3):
                if remote:
                    if not self.incomplete(remote,expected):
                        raise RuntimeError('A different release asset already uses this name: '+path.name)
                    self.remove_incomplete(remote,expected)
                self.record(status='uploading',pending_upload=dict(expected,attempt=attempt+1))
                print(json.dumps({'event':'uploading','asset':path.name,'bytes':expected['bytes'],'attempt':attempt+1}),flush=True)
                result = self.gh('release','upload',self.args.tag,str(path),'--repo',self.args.repository,check=False)
                remote = self.assets().get(path.name)
                if remote and self.matches(remote,expected):
                    break
                # Successful HTTP completion can precede the final digest.
                if result.returncode==0 and remote and not remote.get('digest'):
                    for _ in range(3):
                        time.sleep(2)
                        remote = self.assets().get(path.name)
                        if remote and self.matches(remote,expected):
                            break
                    if remote and self.matches(remote,expected):
                        break
                detail = result.stderr.strip() or result.stdout.strip() or 'GitHub did not finish the upload'
                failure = {'event':'upload_attempt_failed','asset':path.name,'attempt':attempt+1,
                           'exit_code':result.returncode,'error':detail,
                           'remote_state':remote.get('state') if remote else None,
                           'remote_bytes':remote.get('size') if remote else None,
                           'remote_digest':remote.get('digest') if remote else None,
                           'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
                with (self.work/'upload_errors.log').open('a',encoding='utf-8') as log:
                    log.write(json.dumps(failure)+'\n')
                print(json.dumps(failure),flush=True)
                if remote and not self.incomplete(remote,expected):
                    raise RuntimeError('Uploaded asset verification failed: '+path.name+'; '+detail)
                if attempt == 2:
                    raise RuntimeError('Upload did not complete after three attempts: '+path.name+'; '+detail)
                time.sleep(2)
        if not self.matches(remote,expected):
            raise RuntimeError('GitHub did not confirm the asset SHA-256 and size: '+path.name)
        self.state['uploaded_assets'] = [x for x in self.state['uploaded_assets'] if x['filename']!=path.name]
        self.state['uploaded_assets'].append(dict(expected,asset_id=remote['id'],url=remote['browser_download_url']))
        self.record(status='uploading',pending_upload=None,last_error=None)
        print(json.dumps({'event':'asset_verified','asset':path.name,'sha256':expected['sha256']}),flush=True)
        if retire:
            allowed = (self.work/'parts').resolve()
            if path.resolve().parent != allowed or path.stat().st_size != expected['bytes']:
                raise RuntimeError('Temporary part path or size changed; it will not be removed')
            path.unlink()

    def progress(self,information):
        if time.monotonic()-self.last_progress >= 10 or information['files']==information['total_files']:
            print(json.dumps(dict(event='snapshot_progress',**information)),flush=True)
            self.last_progress = time.monotonic()

    def publish(self):
        self.prepare()
        installer = REPO_ROOT/'installer'
        recipe = json.loads((installer/'release.json').read_text(encoding='utf-8-sig'))
        manifest_path = self.work/'package_source.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            rows = json.loads((self.work/'snapshot_inventory.json').read_text())
            if [{k:v for k,v in r.items() if k!='sha256'} for r in rows] != inventory(self.args.source):
                raise RuntimeError('Source changed since the completed snapshot; use a new beta tag')
            assets = self.assets()
            if any(not self.matches(assets.get(p['filename'],{}),p) for p in manifest['parts']):
                raise RuntimeError('A previously uploaded snapshot part is missing or differs')
        else:
            # A failed run may have one incomplete local part. Preserve it under
            # a unique diagnostic name, then deterministically rebuild/compare.
            part_dir = self.work/'parts'
            if part_dir.exists():
                for path in part_dir.iterdir():
                    if path.is_file() and path.name.startswith('Perdition_Payload_v'+self.args.version+'.zip.'):
                        path.rename(self.work/(path.name+'.interrupted.'+str(time.time_ns())))
            manifest = build_snapshot(self.args.source,self.work,self.args.version,self.args.tag,
                f'https://github.com/{self.args.repository}/releases/download/{self.args.tag}',
                callback=lambda path,part:self.upload(path,part,retire=True),
                expected_world_hash=recipe['world_plugin_sha256'],progress=self.progress)
        self.record(status='snapshot_uploaded',archive_sha256=manifest['archive_sha256'],
                    archive_bytes=manifest['archive_bytes'],parts=len(manifest['parts']))
        shutil.copy2(manifest_path,installer/'package_source.json')
        public = REPO_ROOT/'release'
        public.mkdir(exist_ok=True)
        for name in ['snapshot_metadata.json','snapshot_inventory.json']:
            shutil.copy2(self.work/name,public/name)
        setup = installer/('Perdition_Sector_Installer_v'+self.args.version+'_Beta.zip')
        build_inputs = [f for f in installer.rglob('*') if f.is_file() and
            (f.suffix in {'.ps1','.psm1','.py','.cs','.md','.json','.dll','.exe'} or f.name=='RootOverlay.zip')
            and f.name not in {'PerditionSetup.exe','test_results.json'} and not f.name.endswith('.receipt.json')]
        signature = hashlib.sha256()
        for path in sorted(build_inputs):
            signature.update(path.relative_to(installer).as_posix().encode())
            signature.update(bytes.fromhex(digest(path)))
        build_signature = signature.hexdigest()
        if not (setup.is_file() and self.state.get('setup_build_signature')==build_signature
                and self.state.get('setup_sha256')==digest(setup)):
            result = self.run([sys.executable,installer/'build_release.py'])
            print(result.stdout.strip(),flush=True)
            self.record(setup_build_signature=build_signature,setup_sha256=digest(setup))
        self.upload(setup)
        self.upload(manifest_path)
        self.upload(self.work/'snapshot_metadata.json')
        self.upload(self.work/(manifest['archive_name']+'.sha256.txt'))
        assets = self.assets()
        required = manifest['parts']+[{'filename':setup.name,'bytes':setup.stat().st_size,'sha256':digest(setup)}]
        for item in required:
            asset = assets.get(item['filename'])
            if not asset or not self.matches(asset,item):
                raise RuntimeError('Prepublication verification failed: '+item['filename'])
        final_commit = self.commit_sources('Pin beta snapshot manifest and verified release metadata')
        self.gh('release','edit',self.args.tag,'--repo',self.args.repository,
                '--target',final_commit,'--draft=false','--prerelease','--latest=false')
        released = self.gh('api',f'repos/{self.args.repository}/releases/{self.release_id}',json_result=True)
        if released['draft'] or not released['prerelease']:
            raise RuntimeError('GitHub did not confirm the beta publication state')
        # Verify public availability without GitHub credentials, as installers do.
        url = f'https://github.com/{self.args.repository}/releases/download/{self.args.tag}/package_source.json'
        request = urllib.request.Request(url,headers={'User-Agent':'PerditionBetaReleaseCheck/0.2'})
        with urllib.request.urlopen(request,timeout=60) as response:
            downloaded = json.load(response)
        if downloaded != manifest:
            raise RuntimeError('Public snapshot manifest differs from the published installer')
        self.record(status='published',commit=final_commit,public_manifest_verified=True,
            installer_url=f'https://github.com/{self.args.repository}/releases/download/{self.args.tag}/{setup.name}',
            release_url=released['html_url'])
        print(json.dumps({'event':'published','release':released['html_url'],
            'installer':self.state['installer_url'],'parts':len(manifest['parts']),
            'archive_bytes':manifest['archive_bytes'],'archive_sha256':manifest['archive_sha256']}),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(r'C:\Perdition Sector'))
    parser.add_argument('--repository',default='jjc71ps4/Perdition-Sector')
    parser.add_argument('--tag',default='beta-2026.11.20.1')
    parser.add_argument('--version',default='0.2.0-beta.1')
    private = REPO_ROOT.parent/'Private'
    parser.add_argument('--gh',type=Path,default=private/'PublisherTools/bin/gh.exe')
    parser.add_argument('--auth-dir',type=Path,default=private/'GitHubAuth')
    parser.add_argument('--work',type=Path,default=private/'Beta-2026.11.20.1')
    parser.add_argument('--upload-timeout',type=int,default=1800,
                        help='Maximum seconds per upload attempt before retrying (default: 1800)')
    args = parser.parse_args()
    if args.upload_timeout<=0:
        parser.error('--upload-timeout must be positive')
    publisher = Publisher(args)
    try:
        publisher.publish()
    except BaseException as error:
        publisher.record(status='stopped',last_error=str(error))
        raise


if __name__=='__main__':
    try:
        main()
    except BaseException as error:
        print(json.dumps({'event':'stopped','error':str(error),
            'recovery':'Draft release and completed uploads are retained. Resolve the issue and rerun.'}),flush=True)
        sys.exit(1)

