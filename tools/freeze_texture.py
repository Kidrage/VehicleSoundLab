"""Preserve the completed offline investigation separately from DSP releases."""
import json
import shutil
from runtime_review import ROOT,sha

SOURCE=ROOT/'references/analysis/texture_v1'
DEST=ROOT/'baselines/texture_v1'


def main():
    if DEST.exists():raise SystemExit('Preserve existing texture_v1 snapshot.')
    audit=json.loads((SOURCE/'verification.json').read_text(encoding='utf-8'))
    assert audit['result']=='pass' and not audit['runtime_changes']
    for group in ['tools','documents']:
        for name,digest in audit[group].items():assert sha(ROOT/name)==digest,name
    for name,digest in audit['files'].items():assert sha(SOURCE/name)==digest,name
    DEST.mkdir()
    def copy(path,name):
        target=DEST/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    for group in ['tools','documents']:
        for name in audit[group]:copy(ROOT/name,name)
    for path in SOURCE.iterdir():
        if path.is_file() and path.suffix in ['.json','.png']:
            copy(path,Path('review')/path.name)
    copy(SOURCE/'bin/texture_probe.exe',Path('bin/texture_probe.exe'))
    files=[dict(path=str(p.relative_to(DEST)).replace('\\','/'),sha256=sha(p)) for p in sorted(DEST.rglob('*')) if p.is_file()]
    manifest=dict(analysis_version='texture_v1',runtime_version='0.15.0',runtime_changes=False,
        status='Frozen offline evidence and candidate direction. Full V10 sound/driving goal remains active.',
        full_data_workspace_path='references/analysis/texture_v1',raw_media='Approved raw/float masters preserved at canonical paths; no duplicate media.',files=files)
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for item in files:assert sha(DEST/item['path'])==item['sha256']
    print('Frozen offline texture_v1:',len(files),'files verified; runtime V015 unchanged.')


if __name__=='__main__':
    from pathlib import Path
    main()
