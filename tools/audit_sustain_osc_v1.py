"""Verify the isolated sustained-source study and freeze immutable review data."""
from runtime_review import ROOT,sha
import json
import shutil
import urllib.request
import urllib.parse
import numpy as np
import soundfile as sf
from reference_segments import checked_source

OUT=ROOT/'references/analysis/sustain_osc_v1'
SNAPSHOT=ROOT/'baselines/sustain_osc_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    if SNAPSHOT.exists():raise SystemExit('Preserve sustain_osc_v1; use a new version.')
    fit=read(OUT/'fit.json');render=read(OUT/'renders/results.json');browser=read(OUT/'browser_qa.json')
    source=checked_source('A');assert source['master_sha256']==fit['source']['master_sha256']
    assert sha(OUT/'voice.model')==fit['model_sha256']==render['model_sha256']
    arrays=dict(np.load(OUT/'profile_arrays.npz'))
    assert arrays['mean'].shape==(300,4) and arrays['basis'].shape==(300,12,4)
    assert arrays['root'].shape==(300,4,4) and arrays['rho'].shape==(12,) and arrays['residual_rho'].shape==(300,)
    assert fit['statistics']['source_trajectory_stored'] is False and fit['ridge_window_max_spread_hz']<2
    old=read(ROOT/'references/analysis/detail_osc_v1/audit.json')
    expected=dict(old['old_snapshot_manifests']);expected['detail_osc_v1']=sha(ROOT/'baselines/detail_osc_v1/manifest.json')
    snapshots={};total=0
    for manifest in sorted((ROOT/'baselines').glob('*/manifest.json')):
        assert sha(manifest)==expected[manifest.parent.name],manifest
        entries=read(manifest)['files']
        for item in entries:assert sha(manifest.parent/item['path'])==item['sha256'],item['path']
        snapshots[manifest.parent.name]=sha(manifest);total+=len(entries)
    assert len(snapshots)==43 and total==5863
    native=[v for v in read(ROOT/'baselines/v0.20.0/manifest.json')['files']
        if v['path'].replace('\\','/').startswith(('src/','tests/'))]
    for item in native:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    assert len(native)==170
    live=read(ROOT/'references/analysis/detail_osc_v1/verification.json')
    for path,identity in live['source_hashes'].items():assert sha(ROOT/path)==identity,path
    for name,identity in live['binaries'].items():assert sha(ROOT/'build-detail-osc-v1/Release'/name)==identity,name
    for name,item in render['variants'].items():
        path=OUT/f'renders/{name}_float.wav';assert sha(path)==item['float_sha256']
        x,r=sf.read(path,always_2d=True);assert r==48000 and x.shape==(384000,2) and np.isfinite(x).all()
    for name,item in render['audition_files'].items():
        path=OUT/'renders'/item['file'];assert sha(path)==item['sha256']
        x,r=sf.read(path,always_2d=True)
        assert r==48000 and len(x)==item['frames'] and sf.info(path).subtype=='PCM_24' and abs(x).max()<.86
    for name,identity in render['binaries'].items():assert sha(ROOT/'build-sustain-osc-v1/Release'/name)==identity,name
    controls=render['controls'];assert controls['C_vs_independent_complex_sum_max_error']<2e-7
    assert controls['truncated']==controls['invalid']=='rejected'
    assert browser['loads']==5 and not browser['errors']
    assert all(browser[k] for k in ['muted','http_and_file','synth_position_playback_preserved','short_reference_resets','repeat_control','narrow_viewport'])
    http={}
    for name in ['持续OSC统计声源V1.html','持续OSC统计声源V1.md']:
        with urllib.request.urlopen('http://127.0.0.1:8789/research/'+urllib.parse.quote(name),timeout=10) as response:
            assert response.status==200;http[name]=response.status
    files=[p for p in (ROOT/'experiments/sustain_osc_v1').iterdir() if p.is_file()]
    files += [p for p in (ROOT/'tools/sustain_osc_v1').glob('*.py')]
    source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    audit=dict(result='pass',old_snapshot_manifests=snapshots,old_snapshot_files=total,
        native_source_tests_unchanged=len(native),accepted_native_preview_unchanged=True,
        source_hashes=source_hashes,model_sha256=fit['model_sha256'],model_bytes=(OUT/'voice.model').stat().st_size,
        statistical_profile_has_no_time_rows=True,render_controls=controls,browser=browser,http=http,
        native_driving_DSP020_changed=False,new_voice_subjectively_accepted=False,goal_complete=False,
        evidence={str(p.relative_to(ROOT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='audit.json'})
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    files += [p for p in OUT.rglob('*') if p.is_file()]
    files += [ROOT/name for name in ['AGENTS.md','README.md','research/持续OSC统计声源V1.html','research/持续OSC统计声源V1.md',
        'research/goal_progress_sustain_osc_v1.json','research/timbre_quality_20261110.json','research/quality_direction_20261110.json',
        'research/听评记录.md','tools/fit_sustain_osc_v1.py','tools/render_sustain_osc_v1.py',
        'tools/verify_sustain_osc_v1.cjs','tools/audit_sustain_osc_v1.py','tools/seekable_review_player_v1.js',
        'tools/runtime_review.py','tools/reference_segments.py','baselines/v0.20.0/src/io/wav.h','baselines/v0.20.0/bin/vsl_core.lib']]
    files += [ROOT/'build-sustain-osc-v1/Release'/name for name in render['binaries']]
    assert len(files)==len(set(files));SNAPSHOT.mkdir();entries=[]
    for source_path in sorted(files):
        rel=source_path.relative_to(ROOT);dest=SNAPSHOT/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source_path,dest);identity=sha(source_path);assert sha(dest)==identity
        entries.append(dict(path=rel.as_posix(),sha256=identity))
    manifest=dict(version='sustain_osc_v1',scope='Single-context relative-pitch statistical oscillator source; not RPM/load/layer calibrated.',
        subjective_status='New sustained voice pending; previous native default/varispeed accepted.',
        native_driving_application='0.20.0 unchanged',old_snapshot_manifests=snapshots,files=entries)
    (SNAPSHOT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(result='pass',old_snapshots=len(snapshots),old_files=total,native_unchanged=len(native),
        new_snapshot_files=len(entries),model_bytes=(OUT/'voice.model').stat().st_size)))


if __name__=='__main__':main()
