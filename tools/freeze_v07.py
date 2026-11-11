"""Preserve V0.7 source, runtime and selected evidence without replacing history."""
from pathlib import Path
import hashlib
import json
import shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'baselines/v0.7.0'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if OUT.exists():raise SystemExit('V0.7 exists: preserve it and use a new version.')
    audit=json.loads((ROOT/'renders/v0.7.0/workspace_audit.json').read_text())
    assert audit['result']=='pass' and audit['version']=='0.7.0' and audit['ctest_count']==9
    for group in ['source_code','deliverables']:
        for name,digest in audit[group].items():assert sha(ROOT/name)==digest,name
    OUT.mkdir()
    def copy(source,destination=None):
        source=Path(source);target=OUT/(source if destination is None else destination)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/source,target)
    for folder in ['src','tests']:shutil.copytree(ROOT/folder,OUT/folder)
    for name in ['CMakeLists.txt','build.ps1','Launch.cmd','README.md','AGENTS.md']:copy(name)
    binaries=json.loads((ROOT/'renders/v0.7.0/verification.json').read_text())['binaries']
    for name,digest in binaries.items():
        assert sha(ROOT/'build-v07/Release'/name)==digest
        copy(Path('build-v07/Release')/name,Path('bin')/name)
    for name in ['V07断油与泵气激励.md','goal_progress_v07.json','state_evidence_v02.json','upstream_head_v07.json']:
        copy(Path('research')/name)
    for name in audit['deliverables']:
        if name.startswith('tools/'):copy(name)
    for name in ['verification.json','workspace_audit.json','excitation_measurements.json','ctest.xml','ui_smoke.json',
                 'ui_control_roundtrip.ini','browser_qa.json','ui_native_preview.png','ui_detail.png',
                 'listening_desktop.png','listening_mobile.png','dry_lift_sources.png','downshift_fueling.png']:
        copy(Path('renders/v0.7.0')/name,Path('diagnostics')/name)
    copy('renders/v0.7.0/dna_check/dna_pipeline_check.json','diagnostics/dna_pipeline_check.json')
    for path in sorted((ROOT/'renders/v0.7.0').glob('audition_*.wav')):copy(path.relative_to(ROOT),Path('renders')/path.name)
    for path in sorted((ROOT/'renders/v0.7.0').glob('*.csv')):copy(path.relative_to(ROOT),Path('renders')/path.name)
    for name in ['drive_enabled.wav','downshift_enabled.wav']:
        copy(Path('renders/v0.7.0')/name,Path('renders')/name)
    for path in sorted((ROOT/'references/analysis/overrun_v1').iterdir()):
        if path.is_file():copy(path.relative_to(ROOT))
    for name in ['research/upstream/gen/v10_powertrain.gendsp','research/upstream_v6/code/drive_model.js',
                 'research/upstream_snapshot.json','research/v6_control_snapshot.json']:copy(name)
    files=[dict(path=str(p.relative_to(OUT)).replace('\\','/'),sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()]
    manifest=dict(version='v0.7.0',seed=48271,sample_rate=48000,
        status='Frozen fuel-aware excitation review. Broad driving/sound goal remains active and subjective naturalness unverified.',
        upstream_revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',review_workspace_path='research/V07试听.html',
        review_html_sha256=sha(ROOT/'research/V07试听.html'),
        source_media='Approved originals, float masters and full source stems remain at their workspace paths; not duplicated here.',files=files)
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for item in files:assert sha(OUT/item['path'])==item['sha256'],item['path']
    print('Frozen V0.7:',len(files),'files verified')


if __name__=='__main__':main()
