"""Freeze a reviewable driving baseline, not a subjective acceptance."""
import json
import shutil
from pathlib import Path
from runtime_review import ROOT,sha
OUT=ROOT/'baselines/v0.12.0'


def main():
    if OUT.exists():raise SystemExit('V012 exists; preserve it and use a new version.')
    audit=json.loads((ROOT/'renders/v0.12.0/workspace_audit.json').read_text())
    assert audit['result']=='pass' and audit['ctest_count']==14
    for group in ['source_code','deliverables']:
        for name,digest in audit[group].items():assert sha(ROOT/name)==digest,name
    for name,digest in audit['rendered_artifacts'].items():assert sha(ROOT/'renders/v0.12.0'/name)==digest,name
    OUT.mkdir()
    def copy(source,destination=None):
        source=Path(source);target=OUT/(source if destination is None else destination)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/source,target)
    for folder in ['src','tests']:shutil.copytree(ROOT/folder,OUT/folder)
    copy('CMakeLists.txt')
    for name in audit['deliverables']:copy(name)
    report=json.loads((ROOT/'renders/v0.12.0/verification.json').read_text())
    for name,digest in report['binaries'].items():
        assert sha(ROOT/'build-v012/Release'/name)==digest;copy(Path('build-v012/Release')/name,Path('bin')/name)
    for path in sorted((ROOT/'renders/v0.12.0').iterdir()):
        if path.is_file() and (path.suffix in ['.json','.png','.ini','.log','.csv'] or path.name.startswith('audition_')):
            copy(path.relative_to(ROOT),Path('review')/path.name)
    for name in ['research/upstream_v6/code/drive_model.js','research/upstream/gen/v10_powertrain.gendsp']:copy(name)
    files=[dict(path=str(p.relative_to(OUT)).replace('\\','/'),sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()]
    manifest=dict(version='v0.12.0',seed=48271,sample_rate=48000,
        status='Frozen reduced longitudinal review; not identified car dynamics or accepted engine realism. Full goal remains active.',
        review_workspace_path='research/V012试听.html',upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',
        source_media='Original media, float masters and full source stems remain at workspace paths; not duplicated here.',files=files)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for item in files:assert sha(OUT/item['path'])==item['sha256'],item['path']
    print('Frozen V012:',len(files),'files verified. Broad goal remains active.')


if __name__=='__main__':main()
