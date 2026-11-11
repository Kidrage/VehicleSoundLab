"""Read-only historical audit followed by an isolated reviewable snapshot."""
from runtime_review import ROOT,sha
import json
import shutil
import soundfile as sf
import numpy as np

OUT=ROOT/'references/analysis/detail_osc_v1'
SNAPSHOT=ROOT/'baselines/detail_osc_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    if SNAPSHOT.exists():raise SystemExit('Preserve detail_osc_v1 snapshot; use a new version.')
    proof=read(OUT/'verification.json');assert proof['result']=='pass'
    accepted=read(ROOT/'research/timbre_quality_20261110.json')
    for path,key in [(accepted['model'],'model_sha256'),(accepted['quality_reference'],'quality_reference_sha256')]:
        assert sha(ROOT/path)==accepted[key],path
    previous=read(ROOT/'references/analysis/osc_quality_v2/verification.json')
    expected=dict(previous['previous_snapshot_manifests'])
    expected['osc_quality_v2']=sha(ROOT/'baselines/osc_quality_v2/manifest.json')
    snapshots={};total=0
    for manifest in sorted((ROOT/'baselines').glob('*/manifest.json')):
        assert sha(manifest)==expected[manifest.parent.name],manifest
        items=read(manifest)['files']
        for item in items:assert sha(manifest.parent/item['path'])==item['sha256'],item['path']
        snapshots[manifest.parent.name]=sha(manifest);total+=len(items)
    assert len(snapshots)==42 and total==5820
    native=[v for v in read(ROOT/'baselines/v0.20.0/manifest.json')['files']
        if v['path'].replace('\\','/').startswith(('src/','tests/'))]
    for item in native:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    assert len(native)==170
    # Shared coefficient loader and prior preview sources are also immutable.
    for p in (ROOT/'experiments/osc_density_v1').iterdir():
        if p.is_file():assert sha(p)==sha(ROOT/'baselines/osc_quality_v2'/p.relative_to(ROOT))
    for path,identity in read(ROOT/'references/analysis/reference_osc_v2/verification.json')['source_hashes'].items():
        assert sha(ROOT/path)==identity,path
    for path,identity in proof['source_hashes'].items():assert sha(ROOT/path)==identity,path
    for name,identity in proof['binaries'].items():assert sha(ROOT/'build-detail-osc-v1/Release'/name)==identity,name
    for name,item in proof['renders'].items():
        assert sha(OUT/f'{name}_float.wav')==item['float_sha256']
        assert sha(OUT/f'{name}_audition.wav')==item['audition_sha256']
    a,r=sf.read(OUT/'unity_audition.wav');b,s=sf.read(ROOT/accepted['quality_reference'])
    assert r==s==48000 and np.array_equal(a,b)
    device=proof['native']
    assert device['result']=='pass' and device['raw_float_hash']==proof['renders']['unity']['raw_float_hash']
    assert device['queue_empty']==device['live_queue_empty']==0 and device['ui_controls'] and device['live_loops']>=1
    assert .95<device['device_seconds']/device['playback_wall_seconds']<1.03
    assert .95<device['live_device_seconds']/device['live_playback_wall_seconds']<1.03
    assert (OUT/'attempt1/reason.json').exists() and (OUT/'native_preview.png').exists()
    audit=dict(result='pass',old_snapshot_manifests=snapshots,old_snapshot_files=total,
        native_source_tests_unchanged=len(native),old_previews_unchanged=True,unity_PCM24_identical=True,
        quality_reference=accepted,device=device,source_hashes=proof['source_hashes'],binaries=proof['binaries'],
        native_driving_DSP020_changed=False,goal_complete=False,
        limit='Live varispeed monitoring of timed coefficients; not a sustained procedural engine voice.',
        artifacts={str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='audit.json'})
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    files=[p for p in (ROOT/'experiments/detail_osc_v1').iterdir() if p.is_file()]
    files += [p for p in OUT.rglob('*') if p.is_file()]
    files += [ROOT/name for name in ['AGENTS.md','README.md','Launch-detail-osc.cmd',
        'research/细节OSC原生监听V1.md','research/goal_progress_detail_osc_v1.json',
        'research/timbre_quality_20261110.json','research/quality_direction_20261110.json','research/听评记录.md',
        'tools/verify_detail_osc_v1.py','tools/audit_detail_osc_v1.py','tools/runtime_review.py',
        'experiments/osc_density_v1/model.c','experiments/osc_density_v1/model.h',
        'baselines/v0.20.0/src/io/wav.h']]
    files += [ROOT/'build-detail-osc-v1/Release'/name for name in proof['binaries']]
    files += [ROOT/accepted['model'],ROOT/accepted['quality_reference']]
    assert len(files)==len(set(files))
    SNAPSHOT.mkdir();entries=[]
    for source in sorted(files):
        rel=source.relative_to(ROOT);dest=SNAPSHOT/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest);identity=sha(source);assert sha(dest)==identity
        entries.append(dict(path=rel.as_posix(),sha256=identity))
    manifest=dict(version='detail_osc_v1',native_application='0.20.0 unchanged',
        scope='Separate simple C live monitoring; no sustained RPM/load source yet.',
        quality_acceptance='User: detail-preserving reconstruction clearly improved; recording reference normal.',
        live_pitch_subjective_acceptance=False,old_snapshot_manifests=snapshots,files=entries)
    (SNAPSHOT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(result='pass',old_snapshots=len(snapshots),old_files=total,
        native_unchanged=len(native),new_snapshot_files=len(entries),unity_PCM24_identical=True)))


if __name__=='__main__':main()
