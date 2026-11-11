"""Preserve accepted sustained recipe and prior snapshots; freeze native bridge."""
from runtime_review import ROOT,sha
import json
import shutil

OUT=ROOT/'references/analysis/sustain_monitor_v1'
SNAPSHOT=ROOT/'baselines/sustain_monitor_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    if SNAPSHOT.exists():raise SystemExit('Preserve sustain_monitor_v1; use a new version.')
    proof=read(OUT/'verification.json');assert proof['result']=='pass'
    accepted=read(ROOT/'research/sustain_acceptance_20261110.json')
    assert accepted['user_feedback']=='持续声保住了自然质感，方向成立'
    assert sha(ROOT/accepted['model'])==accepted['model_sha256']==proof['profile_sha256']
    frozen=ROOT/'baselines/sustain_osc_v1'
    expected=read(frozen/'references/analysis/sustain_osc_v1/audit.json')['old_snapshot_manifests']
    expected['sustain_osc_v1']=sha(frozen/'manifest.json')
    snapshots={};count=0
    for manifest in sorted((ROOT/'baselines').glob('*/manifest.json')):
        assert sha(manifest)==expected[manifest.parent.name],manifest
        entries=read(manifest)['files']
        for item in entries:assert sha(manifest.parent/item['path'])==item['sha256'],item['path']
        snapshots[manifest.parent.name]=sha(manifest);count+=len(entries)
    assert len(snapshots)==44 and count==5913
    native=[v for v in read(ROOT/'baselines/v0.20.0/manifest.json')['files']
        if v['path'].replace('\\','/').startswith(('src/','tests/'))]
    for item in native:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    assert len(native)==170
    #Accepted earlier preview and all underlying sustained-source experiment files remain exact.
    previous=read(ROOT/'references/analysis/detail_osc_v1/verification.json')
    for path,identity in previous['source_hashes'].items():assert sha(ROOT/path)==identity,path
    for name,identity in previous['binaries'].items():assert sha(ROOT/'build-detail-osc-v1/Release'/name)==identity,name
    frozen_source={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'experiments/sustain_osc_v1').iterdir() if p.is_file()}
    for path,identity in frozen_source.items():assert sha(frozen/path)==identity,path
    for path,identity in proof['source_hashes'].items():assert sha(ROOT/path)==identity,path
    for name,identity in proof['binaries'].items():assert sha(ROOT/'build-sustain-monitor-v1/Release'/name)==identity,name
    for path,identity in proof['evidence'].items():assert sha(ROOT/path)==identity,path
    audit=dict(result='pass',old_snapshot_manifests=snapshots,old_snapshot_files=count,
        native_source_tests_unchanged=len(native),accepted_detail_preview_unchanged=True,
        accepted_sustained_source_unchanged=frozen_source,acceptance=accepted,
        native_source_parity_hash=proof['unmodified_source_float_hash'],
        new_native_subjective_acceptance=False,goal_complete=False,
        evidence={str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='audit.json'})
    (OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    files=[p for p in (ROOT/'experiments/sustain_monitor_v1').iterdir() if p.is_file()]
    files += [p for p in OUT.rglob('*') if p.is_file()]
    files += [ROOT/path for path in ['AGENTS.md','README.md','Launch-sustained-osc.cmd',
        'research/sustain_acceptance_20261110.json','research/持续OSC原生监听V1.md',
        'research/goal_progress_sustain_monitor_v1.json','research/goal_progress_sustain_osc_v1.json',
        'research/timbre_quality_20261110.json','research/听评记录.md',
        'research/持续OSC统计声源V1.html','research/持续OSC统计声源V1.md',
        'tools/verify_sustain_monitor_v1.py','tools/audit_sustain_monitor_v1.py','tools/runtime_review.py',
        'baselines/v0.20.0/src/io/wav.h','baselines/v0.20.0/bin/vsl_core.lib']]
    files += [frozen/path for path in frozen_source]
    files += [ROOT/'build-sustain-monitor-v1/Release'/name for name in proof['binaries']]
    files += [ROOT/accepted['model']]
    assert len(files)==len(set(files));SNAPSHOT.mkdir();entries=[]
    for source in sorted(files):
        rel=source.relative_to(ROOT);dest=SNAPSHOT/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest);identity=sha(source);assert sha(dest)==identity
        entries.append(dict(path=rel.as_posix(),sha256=identity))
    manifest=dict(version='sustain_monitor_v1',scope='Separate live native monitor of accepted single-context sustained OSC recipe.',
        source_subjective_acceptance=accepted['user_feedback'],native_subjective_acceptance='pending',
        native_driving_DSP='0.20.0 unchanged',old_snapshot_manifests=snapshots,files=entries)
    (SNAPSHOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',old_snapshots=len(snapshots),old_files=count,
        new_snapshot_files=len(entries),native_source_tests_unchanged=len(native))))


if __name__=='__main__':main()
