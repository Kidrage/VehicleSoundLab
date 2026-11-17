"""Read every archived byte and nested manifest independently of the finalizer."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def digest(path):
    state=hashlib.sha256()
    with path.open('rb') as stream:
        while value:=stream.read(1024*1024):state.update(value)
    return state.hexdigest()


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.freeze.resolve()
    m=load(root/'manifest.json');assert digest(Path(m['base_freeze'])/'manifest.json')==m['base_manifest_sha256']
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'}
    expected={r['path'] for r in m['files']};assert actual==expected and len(m['files'])==len(expected)
    for row in m['files']:
        file=(root/row['path']).resolve();assert file.is_relative_to(root)
        assert file.stat().st_size==row['bytes'] and digest(file)==row['sha256'],row['path']
    nested=0
    for file in root.rglob('manifest.json'):
        if file==root/'manifest.json':continue
        value=load(file);values=value.get('files',value)
        if not isinstance(values,dict):continue
        for name,expected in values.items():
            if isinstance(expected,str) and len(expected)==64:
                target=(file.parent/name).resolve();assert target.is_relative_to(root)
                assert digest(target)==expected,str(target);nested+=1
    milestone=load(root/'repo/research/startup_material_context_v1_verification.json')
    for name,expected in milestone['source_files'].items():assert digest(root/'repo'/name)==expected,name
    assert milestone['B_audit']['result']==milestone['D_audit']['result']=='passed'
    assert milestone['web']['own_service_closed'] and not milestone['goal_complete']
    report=dict(result='passed',files=len(m['files']),bytes=sum(r['bytes'] for r in m['files']),
        nested_manifest_entries=nested,base_manifest_verified=True,source_bindings_verified=True,
        manifest_sha256=digest(root/'manifest.json'),goal_complete=False)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report,flush=True)


if __name__=='__main__':main()
