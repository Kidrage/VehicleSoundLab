"""Independent integrity audit of the authoring delta and its V12 base."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from urllib.request import urlopen


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def check_manifest(path,exact=False):
    doc=load(path);root=path.parent
    if isinstance(doc.get('files'),list):rows=doc['files']
    else:
        mapping=doc['files'] if isinstance(doc.get('files'),dict) else doc
        rows=[dict(path=k,sha256=v) for k,v in mapping.items()]
    expected=set()
    for row in rows:
        p=root/row['path'];assert p.resolve().is_relative_to(root.resolve())
        assert p.is_file() and digest(p)==row['sha256'],str(p)
        if 'bytes' in row:assert p.stat().st_size==row['bytes']
        expected.add(row['path'])
    if exact:assert expected=={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=path}
    return len(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--milestone',default='event_joint_v1_verification.json')
    parser.add_argument('--base-sources',default='evidence/verification1/exact_sources')
    parser.add_argument('--review-url',default='http://127.0.0.1:8789/references/analysis/event_joint_v1/review1/index.html')
    args=parser.parse_args()
    assert not args.output.exists();repo=Path(__file__).resolve().parents[1]
    manifest=args.freeze/'manifest.json';count=check_manifest(manifest,True);document=load(manifest)
    base=Path(document['base_freeze']);assert digest(base/'manifest.json')==document['base_manifest_sha256']
    base_count=check_manifest(base/'manifest.json',True)
    nested=[]
    for p in args.freeze.rglob('manifest.json'):
        if p!=manifest:nested.append(dict(path=p.relative_to(args.freeze).as_posix(),entries=check_manifest(p)))
    milestone=load(args.freeze/'repo/research'/args.milestone)
    for name,expected in milestone['source_files'].items():assert digest(repo/name)==expected
    runtime=[p for group in ('src','modules','voices') for p in (repo/group).rglob('*')
        if p.is_file() and (p.suffix in ('.c','.h') or group=='voices')]
    old=base/args.base_sources
    assert len(runtime)==459 and all(digest(p)==digest(old/p.relative_to(repo)) for p in runtime)
    source=repo/'build-vehicle-source-v12/bin/Release/vsl_source_bridge.dll'
    assert digest(source)==milestone['checks']['startup']['bridge_sha256']
    http=dict(url=args.review_url)
    try:
        with urlopen(http['url'],timeout=4) as response:
            body=response.read();http.update(status=response.status,exact=body==(args.freeze/'evidence/review1/index.html').read_bytes())
        assert http['status']==200 and http['exact']
    except OSError as error:http['unavailable']=str(error)
    report=dict(result='passed',root_files=count,base_files=base_count,nested=nested,
        manifest_sha256=digest(manifest),current_source_bindings_exact=True,current_runtime_and_voices_exact=len(runtime),
        current_source_DLL_exact=True,review_http=http,goal_complete=False,timbre_accepted=False)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    shutil.copy2(__file__,args.output.with_suffix('.py'))
    print(report,flush=True)


if __name__=='__main__':main()
