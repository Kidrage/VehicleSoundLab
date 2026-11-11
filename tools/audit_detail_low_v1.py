"""Freeze the read-only modulation diagnosis and independent low-PAD candidate."""
from runtime_review import ROOT,sha
import json
import shutil
import numpy as np
import soundfile as sf

SNAPSHOT=ROOT/'baselines/detail_low_v1'
FOLDERS=['references/analysis/detail_modulation_v1','references/analysis/low_body_v1','references/analysis/sustain_monitor_v2']


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    if SNAPSHOT.exists():raise SystemExit('Preserve detail_low_v1; use a new version.')
    diagnosis=read(ROOT/FOLDERS[0]/'analysis.json');low=read(ROOT/FOLDERS[1]/'renders/results.json');native=read(ROOT/FOLDERS[2]/'verification.json')
    browser=read(ROOT/FOLDERS[0]/'browser_qa.json')
    assert diagnosis['result']==low['result']==native['result']=='pass'
    assert diagnosis['source_carrier_phase_identical_at_all_detail_values'] and low['zero_body_exact_previous_native_output']
    assert browser['loads']==7 and not browser['errors'] and browser['muted'] and browser['narrow_viewport']
    assert native['body_checks']['body_phase_error']==0 and native['body_checks']['max_body']>.799
    previous=ROOT/'baselines/sustain_monitor_v1'
    expected=read(previous/'references/analysis/sustain_monitor_v1/audit.json')['old_snapshot_manifests']
    expected['sustain_monitor_v1']=sha(previous/'manifest.json');snapshots={};total=0
    for manifest in sorted((ROOT/'baselines').glob('*/manifest.json')):
        assert sha(manifest)==expected[manifest.parent.name],manifest
        entries=read(manifest)['files']
        for item in entries:assert sha(manifest.parent/item['path'])==item['sha256'],item['path']
        snapshots[manifest.parent.name]=sha(manifest);total+=len(entries)
    assert len(snapshots)==45 and total==5959
    main=[v for v in read(ROOT/'baselines/v0.20.0/manifest.json')['files'] if v['path'].replace('\\','/').startswith(('src/','tests/'))]
    for item in main:assert sha(ROOT/item['path'])==item['sha256']
    assert len(main)==170
    for rel in ['detail_osc_v1','sustain_monitor_v1']:
        proof=read(ROOT/'references/analysis'/rel/'verification.json')
        for path,identity in proof['source_hashes'].items():assert sha(ROOT/path)==identity,path
        build={'detail_osc_v1':'build-detail-osc-v1','sustain_monitor_v1':'build-sustain-monitor-v1'}[rel]
        for name,identity in proof['binaries'].items():assert sha(ROOT/build/'Release'/name)==identity,name
    for proof,build in [(diagnosis,'build-detail-modulation-audit-v1'),(native,'build-sustain-monitor-v2')]:
        for path,identity in proof['source_hashes'].items():assert sha(ROOT/path)==identity,path
        for name,identity in proof['binaries'].items():assert sha(ROOT/build/'Release'/name)==identity,name
    assert sha(ROOT/'references/analysis/sustain_osc_v1/voice.model')==diagnosis['model_sha256']==low['unchanged_core_profile_sha256']
    assert sha(ROOT/'references/analysis/low_body_v1/body.model')==low['low_profile_sha256']==native['body_profile_sha256']
    for name,item in low['variants'].items():
        if name=='solo':assert sha(ROOT/FOLDERS[1]/'renders/body_solo_audition.wav')==item['sha256'];continue
        for suffix,key in [('mix_float','mix_float_sha256'),('body_float','body_float_sha256'),('audition','audition_sha256')]:
            assert sha(ROOT/FOLDERS[1]/'renders'/f'{name}_{suffix}.wav')==item[key]
    a,r=sf.read(ROOT/FOLDERS[0]/'detail100_audition.wav');b,s=sf.read(ROOT/'references/analysis/sustain_osc_v1/renders/generated_audition.wav')
    assert r==s==48000 and np.array_equal(a,b)
    audit=dict(result='pass',old_snapshot_manifests=snapshots,old_snapshot_files=total,native_source_tests_unchanged=len(main),
        previous_previews_unchanged=True,default_audition_exact=True,new_zero_low_layer_exact=True,
        modulation_fix_subjectively_accepted=False,low_layer_subjectively_accepted=False,goal_complete=False,
        limits='No detected carrier/pitch routing bug; complex modulation mechanism needs ablation listening. Low PAD is a recording-informed engineering addition, not isolated physical-source or RPM calibration.',
        artifacts={str(p.relative_to(ROOT)):sha(p) for folder in FOLDERS for p in (ROOT/folder).rglob('*') if p.is_file()})
    (ROOT/FOLDERS[2]/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    files=[p for folder in FOLDERS for p in (ROOT/folder).rglob('*') if p.is_file()]
    for folder in ['experiments/detail_modulation_audit_v1','experiments/low_body_v1','experiments/sustain_monitor_v2',
        'baselines/sustain_osc_v1/experiments/sustain_osc_v1']:
        files += [p for p in (ROOT/folder).iterdir() if p.is_file()]
    files += [ROOT/path for path in ['AGENTS.md','README.md','Launch-sustained-low.cmd',
        'research/持续OSC细节与低频V1.html','research/持续OSC细节与低频V1.md','research/sustain_acceptance_20261110.json',
        'research/goal_progress_detail_low_v1.json','research/goal_progress_sustain_monitor_v1.json','research/听评记录.md',
        'tools/analyze_detail_modulation_v1.py','tools/finish_detail_modulation_v1.py','tools/fit_low_body_v1.py',
        'tools/render_low_body_v1.py','tools/verify_sustain_monitor_v2.py','tools/verify_detail_low_v1.cjs','tools/audit_detail_low_v1.py',
        'tools/runtime_review.py','tools/reference_segments.py','tools/seekable_review_player_v1.js',
        'baselines/v0.20.0/src/io/wav.h','baselines/v0.20.0/bin/vsl_core.lib',
        'references/analysis/sustain_osc_v1/voice.model','references/analysis/sustain_osc_v1/ridge_observations.npz']]
    for proof,build in [(diagnosis,'build-detail-modulation-audit-v1'),(native,'build-sustain-monitor-v2')]:
        files += [ROOT/build/'Release'/name for name in proof['binaries']]
    assert len(files)==len(set(files));SNAPSHOT.mkdir();entries=[]
    for source in sorted(files):
        rel=source.relative_to(ROOT);dest=SNAPSHOT/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest);identity=sha(source);assert sha(dest)==identity
        entries.append(dict(path=rel.as_posix(),sha256=identity))
    (SNAPSHOT/'manifest.json').write_text(json.dumps(dict(version='detail_low_v1',scope='Read-only complex-modulation diagnosis, phase-fixed ablation and new independent low-PAD candidate/native monitor.',
        subjective_status='Native bounded pitch accepted; above70% detail reported oscillatory. Ablation and new low layer pending.',
        main_driving_DSP='0.20.0 unchanged',old_snapshot_manifests=snapshots,files=entries),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',old_snapshots=len(snapshots),old_files=total,new_snapshot_files=len(entries),native_source_tests_unchanged=len(main))))


if __name__=='__main__':main()
