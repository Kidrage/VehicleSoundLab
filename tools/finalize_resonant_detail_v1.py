"""Bind dry auditions and serialize the source model as parameters only."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False);root=a.workspace/'references/analysis/resonant_detail_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
fit=read(root/'fit1/report.json');model=read(root/'fit1/detail_model.json')
render=read(root/'render1/report.json');review=read(root/'review1/report.json')
assert fit['result']=='fit_and_known_controls_pass' and render['result']=='render_technical_pass'
assert review['result']=='35_clips_HTTP_decode_pass'
for report in (fit,render):
    for name,digest in report['source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in fit['input_sha256'].items():assert sha(Path(name))==digest,name
assert sha(repo/'tools/review_resonant_detail_v1.py')==review['source_sha256']
assert sha(root/'review1/index.html')==review['page_sha256']
for row in review['clips']:assert sha(root/'review1'/row['file'])==row['sha256']
done=subprocess.run(['node','--check',str(root/'review1/player.js')],capture_output=True,timeout=15)
(a.out/'javascript_syntax.log').write_bytes(done.stdout+done.stderr);assert done.returncode==0
accepted=read(repo/'research/coherent_low_v1_acceptance.json')
assert sha(repo/accepted['model'])==accepted['model_sha256']
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:index=list(csv.DictReader(stream))
assert len(index)==478
for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
profile=dict(schema='vsl.resonant-detail-offline/1',sample_rate=48000,acoustic_root_hz=46.875,
    original_DNA=dict(file='voices/dna_bank_v1/V10 Exterior.model',sha256=accepted['dna_model_sha256']),
    independent_LF=dict(file=accepted['model'],sha256=accepted['model_sha256'],scale=accepted['low_scale']),
    kernel=dict(AR_order=24,warmup_frames=model['plan']['warmup_frames'],cycle_frames=1024,
        excitation='independent band xorshift64star/BoxMuller, stream seed XOR masked golden-ratio multiple',
        band_seed_multiplier_hex='9E3779B97F4A7C15',stereo_R_over_L=model['stereo_R_over_L']),
    filters=model['filters'],presets=[dict(name=t['label'],harmonic_power_reduction=t['amount'],
        harmonic_transition_hz=model['plan']['harmonic_transition_hz'],detail_amplitude_gain=t['noise_amplitude_gain'])
        for t in model['trials'] if t['amount']],
    source_trajectory_stored=False,room_model=False,physical_modes_identified=False,human_accepted=False,
    scope=model['plan']['scope'])
voice=repo/'voices/resonant_detail_v1/detail.json';voice.parent.mkdir(parents=True,exist_ok=True)
voice.write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
trials=[]
for amount in model['plan']['replacement_amounts']:
    rows=[x for x in render['trials'] if x['amount']==amount]
    repeat=[x['observation'][-1]['repeat'][0]['maximum_repeat'] for x in rows]
    trials.append(dict(amount=amount,seeds=[x['seed'] for x in rows],
        maximum_mean_band_error_db=max(x['maximum_mean_power_error_db'] for x in rows),
        maximum_complex_coherence_error=max(x['maximum_complex_coherence_error'] for x in rows),
        repeat_6_8k_first_block_left_range=[min(repeat),max(repeat)],
        maximum_peak_FS_common_gain=max(x['peak_FS_after_common_gain'] for x in rows)))
r=dict(schema='vsl.resonant-detail-summary/1',date='2026-11-12',result='offline_candidate_technical_pass_only',
    model_profile=str(voice.relative_to(repo)).replace('\\','/'),model_sha256=sha(voice),
    controls=fit['controls'],maximum_pole_radius=max(x['pole_radius'] for x in model['filters']),
    trials=trials,C_H_unchanged=478,Ctests_not_repeated=47,no_native_or_driver_changes=True,
    independent_LF_preserved=True,source_trajectory_stored=False,new_width_information=False,
    listening='pending',manual_browser_interaction=False,javascript_syntax_pass=True,
    review_URL=review['url'],review_clips=35,
    evidence_sha256={str(p.relative_to(root)):sha(p) for p in [root/'fit1/report.json',root/'render1/report.json',root/'review1/report.json']},
    limits=['Same1.217s normalized A training source; not raw-engine/RPM/state/other-engine calibration',
            'AR poles fit colour, not identified physical friction/exhaust modes',
            'Uniform replacement amounts can over-diffuse middle bands while highest band remains too periodic',
            'Weak validated envelope is not complete source time dynamics; recorded transfer remains embedded',
            'Statistics/mean energy/decode checks do not establish naturalness or real12speaker/longrun acceptance'])
(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
(repo/'research/resonant_detail_v1_summary.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(__file__,a.out/'executed_finalize.py')
print(json.dumps(dict(result=r['result'],trials=trials,model=r['model_profile'])))
