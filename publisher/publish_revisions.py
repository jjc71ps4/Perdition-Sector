"""GitHub Actions publisher for verified, externally transferred build artifacts.

Transport blobs are temporary Git objects, never files in the repository tree.
After publishing, normal clones contain source and receipts, not player assets.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import base64,hashlib,json,os,subprocess,sys,time,urllib.request,zipfile

def digest(path):
    with path.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(*args):return subprocess.check_output(args,text=True).strip()
def api(path):
    req=urllib.request.Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/'+path,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'PerditionBetaPublisher'})
    with urllib.request.urlopen(req,timeout=120)as response:return json.load(response)
def main():
    definition=Path(sys.argv[1]);manifest=json.loads(definition.read_text());folder=Path('published-artifacts');folder.mkdir(exist_ok=True)
    tag=manifest['tag'];repo=os.environ['GITHUB_REPOSITORY'];release=None
    release=next((r for r in api('releases?per_page=100')if r['tag_name']==tag),None)
    if release is None:
        run('gh','api','--method','POST','repos/'+repo+'/releases','-f','tag_name='+tag,'-f','target_commitish='+os.environ['GITHUB_SHA'],'-f','name='+manifest['title'],'-F','draft=true','-F','prerelease=true','-F','body=@'+manifest['notes_file'])
        release=next(r for r in api('releases?per_page=100')if r['tag_name']==tag)
    def chunk(item):
        result=api('git/blobs/'+item['git_sha']);data=base64.b64decode(result['content'])
        assert len(data)==item['bytes']and hashlib.sha256(data).hexdigest()==item['sha256'],'Transport chunk failed verification'
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==item['git_sha']
        return data
    verified=[]
    for item in manifest['artifacts']:
        filename=item['filename'];assert Path(filename).name==filename and filename.endswith('.zip')
        path=folder/filename
        existing=next((a for a in api('releases/'+str(release['id']))['assets']if a['name']==filename),None)
        if existing and existing['state']!='uploaded'and not existing.get('digest')and release['draft']:
            run('gh','api','--method','DELETE','repos/'+repo+'/releases/assets/'+str(existing['id']));existing=None
        if existing:
            assert existing['state']=='uploaded'and existing['size']==item['bytes'],'Conflicting or incomplete asset is preserved'
            with path.open('wb')as download:subprocess.run(['gh','api','repos/'+repo+'/releases/assets/'+str(existing['id']),'-H','Accept: application/octet-stream'],stdout=download,check=True)
        else:
            print('Reconstructing '+filename,flush=True)
            with ThreadPoolExecutor(max_workers=4)as pool, path.open('wb')as output:
                for data in pool.map(chunk,item['chunks']):output.write(data)
            assert path.stat().st_size==item['bytes']and digest(path)==item['sha256'],'Reconstructed artifact failed verification'
            with zipfile.ZipFile(path)as archive:assert archive.testzip()is None
            run('gh','api','--method','POST','https://uploads.github.com/repos/'+repo+'/releases/'+str(release['id'])+'/assets?name='+filename,'-H','Content-Type: application/zip','--input',str(path))
        assert digest(path)==item['sha256']
        asset=next(a for a in api('releases/'+str(release['id']))['assets']if a['name']==filename)
        assert asset['state']=='uploaded'and asset['size']==item['bytes']
        if asset.get('digest'):assert asset['digest']=='sha256:'+item['sha256']
        else:
            check=folder/'verified-download';check.mkdir(exist_ok=True)
            with (check/filename).open('wb')as download:subprocess.run(['gh','api','repos/'+repo+'/releases/assets/'+str(asset['id']),'-H','Accept: application/octet-stream'],stdout=download,check=True)
            assert digest(check/filename)==item['sha256']
        verified.append({'name':filename,'bytes':item['bytes'],'sha256':item['sha256'],'url':asset['browser_download_url']})
        print('Verified release asset '+filename,flush=True)
    run('gh','api','--method','PATCH','repos/'+repo+'/releases/'+str(release['id']),'-F','draft=false','-F','prerelease=true')
    # Publish the channel only after every referenced release asset is verified.
    run('git','pull','--ff-only','origin','main')
    candidate=Path(manifest['channel_candidate']);channel=Path('updates/beta-v2.json');channel.write_bytes(candidate.read_bytes())
    receipt={'tag':tag,'assets':verified,'base_archive_reuploaded':False,'channel':'updates/beta-v2.json','workflow_run':os.environ['GITHUB_RUN_ID'],'source_commit':os.environ['GITHUB_SHA'],'complete':True}
    receipt_path=Path(manifest['publication_receipt']);receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    for key,destination in [('readme_candidate','README.md'),('channel_readme_candidate','updates/README.md')]:
        Path(destination).write_bytes(Path(manifest[key]).read_bytes())
    Path('RELEASE_NOTES.md').write_bytes(Path(manifest['notes_file']).read_bytes())
    definition.unlink()
    run('git','config','user.name','github-actions[bot]');run('git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    run('git','add',str(channel),str(receipt_path),str(definition),'README.md','RELEASE_NOTES.md','updates/README.md')
    if run('git','diff','--cached','--name-only'):
        run('git','commit','-m','Publish verified 0.2.3 beta assets and update channel');run('git','push','origin','HEAD:main')
    print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
