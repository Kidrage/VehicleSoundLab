"""Freeze a verified version without modifying historical source/media."""
import json
import shutil
from pathlib import Path
from runtime_review import ROOT,sha


def freeze(version,build_tag,ctests,review_path,status,upstream_revision):
    out=ROOT/'baselines'/('v'+version);rendered=ROOT/'renders'/('v'+version)
    if out.exists():raise SystemExit(f'{out.name} exists; preserve it and use a new version.')
    audit=json.loads((rendered/'workspace_audit.json').read_text())
    assert audit['result']=='pass' and audit['ctest_count']==ctests and audit['version']==version
    for group in ['source_code','deliverables']:
        for name,digest in audit[group].items():assert sha(ROOT/name)==digest,name
    for name,digest in audit['rendered_artifacts'].items():assert sha(rendered/name)==digest,name
    out.mkdir()
    def copy(source,destination=None):
        source=Path(source);target=out/(source if destination is None else destination)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/source,target)
    for folder in ['src','tests']:shutil.copytree(ROOT/folder,out/folder)
    copy('CMakeLists.txt')
    for name in audit['deliverables']:copy(name)
    report=json.loads((rendered/'verification.json').read_text())
    for name,digest in report['binaries'].items():
        source=Path('build-'+build_tag)/'Release'/name
        assert sha(ROOT/source)==digest;copy(source,Path('bin')/name)
    for path in sorted(rendered.iterdir()):
        if path.is_file() and (path.suffix in ['.json','.png','.ini','.log','.csv','.vsltake'] or path.name.startswith('audition_')):
            copy(path.relative_to(ROOT),Path('review')/path.name)
    for name in ['research/upstream_v6/code/drive_model.js','research/upstream/gen/v10_powertrain.gendsp']:copy(name)
    files=[dict(path=str(p.relative_to(out)).replace('\\','/'),sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
    manifest=dict(version='v'+version,seed=48271,sample_rate=48000,status=status,
        review_workspace_path=review_path,upstream_revision=upstream_revision,
        source_media='Original media, float masters and full source stems remain at workspace paths; not duplicated here.',files=files)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for item in files:assert sha(out/item['path'])==item['sha256'],item['path']
    print('Frozen',out.name,':',len(files),'files verified. Broad goal remains active.')
