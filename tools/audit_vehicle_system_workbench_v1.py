"""Independent byte audit of every file, including nested manifests, in a delta."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(file):
    h=hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=a.freeze.resolve();manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    rows=manifest['files'];assert len(rows)==len({r['path'] for r in rows})
    actual={f.relative_to(root).as_posix() for f in root.rglob('*') if f.is_file() and f!=root/'manifest.json'}
    assert actual=={r['path'] for r in rows}
    for row in rows:
        file=(root/row['path']).resolve();assert file.is_relative_to(root)
        assert file.stat().st_size==row['bytes'] and digest(file)==row['sha256'],row['path']
    base=Path(manifest['base_freeze'])/'manifest.json'
    assert digest(base)==manifest['base_manifest_sha256']
    proof=json.loads((root/'repo/research/vehicle_system_workbench_v1_verification.json').read_text(encoding='utf-8'))
    assert proof['result']=='passed' and proof['ui']['underflows']==0 and not proof['goal_complete']
    assert proof['ui']['event_start_counts']==proof['native']['event_start_counts']
    assert proof['web']['preset_sha256']==digest(root/'evidence/web1/browser.preset.json')
    result=dict(result='passed',files=len(rows),bytes=sum(r['bytes'] for r in rows),
        nested_manifests_included=True,base_manifest_exact=True,manifest_sha256=digest(root/'manifest.json'),goal_complete=False)
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
