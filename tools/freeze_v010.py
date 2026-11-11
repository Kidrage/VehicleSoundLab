"""Freeze the review candidate without declaring the full driving goal complete."""
import json
import shutil
from pathlib import Path
from runtime_review import ROOT,sha
OUT=ROOT/'baselines/v0.10.0'


def main():
    if OUT.exists():raise SystemExit('V010 exists; preserve it and use a new version.')
    audit=json.loads((ROOT/'renders/v0.10.0/workspace_audit.json').read_text())
    assert audit['result']=='pass' and audit['ctest_count']==12
    for group in ['source_code','deliverables','reference_artifacts']:
        for name,digest in audit[group].items():assert sha(ROOT/name)==digest,name
    for name,digest in audit['rendered_artifacts'].items():assert sha(ROOT/'renders/v0.10.0'/name)==digest,name
    OUT.mkdir()
    def copy(source,destination=None):
        source=Path(source);target=OUT/(source if destination is None else destination)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/source,target)
    for folder in ['src','tests']:shutil.copytree(ROOT/folder,OUT/folder)
    for group in ['deliverables','reference_artifacts']:
        for name in audit[group]:copy(name)
    copy('CMakeLists.txt')
    report=json.loads((ROOT/'renders/v0.10.0/verification.json').read_text())
    for name,digest in report['binaries'].items():
        assert sha(ROOT/'build-v010/Release'/name)==digest;copy(Path('build-v010/Release')/name,Path('bin')/name)
    for path in sorted((ROOT/'renders/v0.10.0').iterdir()):
        if path.is_file() and (path.suffix in ['.json','.png','.ini','.xml','.csv'] or path.name.startswith('audition_')):
            copy(path.relative_to(ROOT),Path('review')/path.name)
    copy('research/upstream_v6/code/drive_model.js')
    files=[dict(path=str(p.relative_to(OUT)).replace('\\','/'),sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()]
    manifest=dict(version='v0.10.0',seed=48271,sample_rate=48000,
        status='Frozen continuous-start engineering review. Full goal active: high-RPM timbre, physical dynamics, measured state maps and actual spatial listening incomplete.',
        upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',review_workspace_path='research/V010试听.html',
        source_media='Original media, float masters and full object stems remain at workspace paths; not duplicated here.',files=files)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for item in files:assert sha(OUT/item['path'])==item['sha256'],item['path']
    print('Frozen V010:',len(files),'files verified. Broad goal remains active.')


if __name__=='__main__':main()
