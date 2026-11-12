"""Bind source/context evidence and publish a separate parameter-only low voice."""
import argparse,csv,json,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False)
root=a.workspace/'references/analysis/idle_resonant_v1';context=a.workspace/'references/analysis/idle_context_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
fit=read(root/'fit1/report.json');model=read(root/'fit1/detail_model.json')
render=read(root/'render1/report.json');review=read(root/'review1/report.json');audit=read(context/'analysis1/report.json')
assert fit['result']=='fit_and_fractional_period_controls_pass' and render['result']=='render_technical_pass'
assert review['result']=='review_technical_pass' and audit['result']=='diagnostic_controls_pass'
for report in (fit,render,audit):
    for name,digest in report['source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in report['input_sha256'].items():assert sha(Path(name))==digest,name
for name,digest in review['source_sha256'].items():assert sha(repo/name)==digest,name
assert sha(root/'review1/index.html')==review['page_sha256']
for row in review['clips']:assert sha(root/'review1'/row['file'])==row['sha256']
context_frames=0
for folder in ('inspect1','inspect2'):
    report=read(context/folder/'report.json')
    # Preserve and verify the exact historical executed script, including the
    # first version before optional-plan support was added for inspection2.
    assert sha(context/folder/'executed_inspect.py')==report['source_sha256']
    for key,source in report['sources'].items():
        assert sha(Path(source['video']))==source['video_sha256']
        for row in source['frames']+source['boards']:
            assert sha(context/folder/key/row['file'])==row['sha256']
        context_frames+=len(source['frames'])
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
assert len(index)==478
for row in index:assert sha(repo/row['文件'])==row['SHA-256']
filters=[]
for m in model['filters']:
    filters.append({k:m[k] for k in ('band_hz','a','sos','sigma','pole_radius')}|dict(
        envelope={k:m['envelope'][k] for k in ('coefficients','enabled')}))
original=repo/audit['plan']['base_model']
profile=dict(schema='vsl.idle-resonant-offline/1',sample_rate=48000,acoustic_root_hz=model['root_hz'],
    state_label='stationary_low_candidate_not_confirmed_warm_idle',source_trajectory_stored=False,
    original_DNA=dict(file=original.relative_to(repo).as_posix(),sha256=sha(original)),
    kernel=dict(warmup_frames=96000,cycle_frames=model['plan']['cycle_frames'],
        excitation='existing xorshift64star/BoxMuller with independent band seeds',
        band_seed_rule='seed XOR ((0x9E3779B97F4A7C15 * (band+1)) mod 2^64)'),
    filters=filters,stereo_R_over_L=model['stereo_R_over_L'],
    presets=[dict(name=t['label'],harmonic_power_reduction=t['amount'],
        harmonic_transition_hz=model['plan']['harmonic_transition_hz'],detail_gain=t['detail_gain']) for t in model['trials']],
    confirmed_RPM=None,confirmed_thermal_state=None,added_low_body=False,room_model=False,
    physical_modes_identified=False,native_C_detail_kernel=False,human_accepted=False)
voice=repo/'voices/idle_resonant_v1/detail.json';voice.parent.mkdir(parents=True,exist_ok=True)
voice.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
trials=[]
for label in ('add_only','replace35'):
    rows=[t for t in render['trials'] if t['label']==label]
    trials.append(dict(label=label,seeds=[t['seed'] for t in rows],
        maximum_power_error_db=max(t['maximum_power_error_db'] for t in rows),
        maximum_coherence_error=max(t['maximum_complex_coherence_error'] for t in rows),
        maximum_peak_FS_common_gain=max(t['peak_FS_after_common_gain'] for t in rows),
        maximum_absolute20_300Hz_change_db=max(abs(v) for t in rows for v in t['low20_300_change_db']),
        repeat_first_block_left=[dict(band_hz=rows[0]['observation'][i]['band_hz'],
            range=[min(t['observation'][i]['repeat'][0]['maximum_repeat'] for t in rows),
                   max(t['observation'][i]['repeat'][0]['maximum_repeat'] for t in rows)]) for i in range(5)]))
selection=repo/'voices/resonant_detail_v1/SELECTION.json';held=read(selection)
assert held['preset']=='replace_35' and sha(selection.parent/held['profile'])==held['profile_sha256']
r=dict(schema='vsl.idle-resonant-summary/1',date='2026-11-12',result='offline_candidate_technical_pass_only',
    source_seconds=[243.9,247.1],acoustic_root_hz=model['root_hz'],source_RPM=None,source_thermal_state=None,
    context_frames_inspected=context_frames,annotations='research/idle_context_v1_annotations.json',
    annotations_sha256=sha(repo/'research/idle_context_v1_annotations.json'),
    profile_file=voice.relative_to(repo).as_posix(),profile_sha256=sha(voice),controls=fit['controls'],
    maximum_pole_radius=fit['maximum_pole_radius'],enabled_envelope_bands=fit['enabled_envelope_bands'],
    trials=trials,C_H_unchanged=478,Ctests_not_repeated=47,moving_selection_sha256=sha(selection),
    moving_reference_changed=False,no_native_default_driver_or_take_changes=True,listening='pending',
    review_URL=review['url'],review_clips=35,HTTP_FFmpeg_JS_pass=True,manual_browser_interaction=False,
    evidence_sha256={str(path.relative_to(a.workspace)).replace('\\','/'):sha(path) for path in
        [context/'inspect1/report.json',context/'inspect2/report.json',context/'analysis1/report.json',
         root/'fit1/report.json',root/'render1/report.json',root/'review1/report.json']},
    limits=['Not confirmed warm idle, measured engine RPM, physical source separation or full-state calibration',
        'All periodic detail envelopes disabled;2.2–3k passed half validation but exceeded the predeclared weak-depth bound',
        '3–8k source coverage restored only as a candidate; above8k is not fitted by this source profile',
        'Rank-one shared stereo is a near-mono approximation; no new width or physical speaker information',
        'Fixed-pitch offline source only; no detail pitch/load/state driver port or listening acceptance',
        'Band powers, period repeats and stability do not establish mechanical naturalness'])
for path in (a.out/'report.json',repo/'research/idle_resonant_v1_summary.json'):
    path.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(__file__,a.out/'executed_finalize.py')
print(json.dumps(dict(result=r['result'],frames=context_frames,trials=trials,review_URL=review['url'])))
