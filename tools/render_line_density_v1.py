"""Existing fixed-phase C DNA plus independent C residual, bounded separate trials."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--analysis',type=Path,required=True)
parser.add_argument('--dna-probe',type=Path,required=True)
parser.add_argument('--residual-probe',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from harmonic_magnitude_v1.legacy import parse,render as direct_sum
from sustain_osc_v1.profile import export as export_dna
from residual_osc_v1.fit import fit,export as export_residual
from residual_osc_v1.spectrum import matrices,error
from line_density_v1.profiles import scale
from line_density_v1.measure import measure
from line_density_v1.review import save_review,page

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/line_density_render_v1_plan.json'
plan=json.loads(plan_path.read_text(encoding='utf-8'))
measure_plan=json.loads((repo/'research/line_density_v1_plan.json').read_text(encoding='utf-8'))
paths=[Path(__file__),plan_path,repo/'research/line_density_v1_plan.json',repo/'research/coherent_low_v1_acceptance.json',
    repo/'tools/drive_evidence_v1/sources.py',repo/'tools/harmonic_magnitude_v1/legacy.py',
    repo/'tools/sustain_osc_v1/profile.py',repo/'tools/sustain_osc_v1/oracle.py',
    *sorted((repo/'tools/line_density_v1').glob('*.py')),*sorted((repo/'tools/residual_osc_v1').glob('*.py')),
    *sorted((repo/'modules/sound_dna').glob('*.[ch]')),*sorted((repo/'modules/sound_residual').glob('*.[ch]')),
    *[repo/name for name in ('handoff/CMakeLists.txt','experiments/sustain_monitor_v3/probe.c',
       'experiments/sustain_monitor_v3/render.c','experiments/sustain_monitor_v3/render.h','experiments/residual_osc_v1/probe.c')]]
for p in paths:
    target=args.out/'exact_sources'/p.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
r=dict(schema='vsl.line-density-render/1',result='running',trials=[],commands=[],input_sha256={},
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
(args.out/'metadata.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')


def bound(root,name):
    manifest=root/'manifest.json'
    expected=next(row['sha256'] for row in json.loads(manifest.read_text(encoding='utf-8'))['files'] if row['path']==name)
    assert sha(root/name)==expected,name
    r['input_sha256'][str(root/name)]=expected;r['input_sha256'][str(manifest)]=sha(manifest)
    return root/name


def invoke(command):
    result=subprocess.run([str(v) for v in command],capture_output=True,text=True,timeout=120)
    r['commands'].append(dict(command=[str(v) for v in command],exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
    result.check_returncode()
    audio,rate=sf.read(command[2],always_2d=True)
    assert rate==48000 and len(audio)==round(plan['seconds']*48000) and np.isfinite(audio).all()
    return audio


try:
    diagnostic=json.loads((args.analysis/'report.json').read_text(encoding='utf-8'))
    assert diagnostic['result']=='diagnostics_completed' and diagnostic['diagnostic_gate']['separate_experimental_C_render_eligible']
    for name,digest in diagnostic['source_sha256'].items():assert sha(args.analysis/'exact_sources'/name)==digest
    r['input_sha256'][str(args.analysis/'report.json')]=sha(args.analysis/'report.json')
    for probe in (args.dna_probe,args.residual_probe):r['input_sha256'][str(probe)]=sha(probe)
    acceptance=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    assert sha(repo/acceptance['model'])==acceptance['model_sha256']
    dna_path=repo/'voices/dna_bank_v1/V10 Exterior.model'
    assert sha(dna_path)==acceptance['dna_model_sha256'];r['input_sha256'][str(dna_path)]=sha(dna_path)
    frozen=args.workspace/'baselines/coherent_low_v1'
    low,rate=sf.read(bound(frozen,'evidence/raw/measured.wav'),always_2d=True)
    old_dna,old_rate=sf.read(bound(frozen,'evidence/raw/dna.wav'),always_2d=True)
    reference,ref_rate=sf.read(bound(args.workspace/'baselines/residual_motion_v1','evidence/fit1/reference.wav'),always_2d=True)
    assert rate==old_rate==ref_rate==48000 and len(low)>=round(plan['seconds']*48000)
    low=low[:round(plan['seconds']*48000)]*acceptance['low_scale']
    model=parse(dna_path);raw=args.out/'raw';raw.mkdir();models=args.out/'models';models.mkdir()
    original=invoke([args.dna_probe,dna_path,raw/'original_dna.wav',plan['seconds'],1,1,1])
    assert np.array_equal(original[:len(old_dna)],old_dna)
    accepted=original+low
    sf.write(raw/'accepted.wav',accepted,48000,subtype='FLOAT')
    target=matrices(reference);warm=plan['warmup_frames'];review=dict(accepted=accepted)
    nref=len(reference);baseline_measure,_=measure(accepted[24000:24000+nref],measure_plan,16)
    base_concentration=np.array(baseline_measure['rows'][0]['concentration_LR'])
    for amount in plan['power_reduction_amounts']:
        name='density_'+str(round(amount*100));scaled,gain=scale(model,amount,plan['transition_hz'])
        profile=models/(name+'.model');export_dna(profile,scaled)
        dna=invoke([args.dna_probe,profile,raw/(name+'_dna.wav'),plan['seconds'],1,1,1])
        if amount==0:assert np.array_equal(dna,original)
        else:
            _,removed,_=direct_sum(model,plan['direct_sum_check_frames'],plan['dna_seed'],1-gain)
            delta=original[:len(removed)]-dna[:len(removed)]
            direct_error=float(np.max(abs(delta-removed)))
            assert direct_error<plan['tolerances']['C_direct_sum_maximum_FS_error'],direct_error
        base=dna+low
        residual_rows,fit_info=fit(reference,base[warm:])
        residual_profile=models/(name+'.residual');export_residual(residual_profile,residual_rows)
        trial=dict(amount=amount,name=name,dna_model_sha256=sha(profile),residual_model_sha256=sha(residual_profile),
            low_model_unchanged=True,low_rows_exact=True,common_channel_gains=True,
            maximum_C_subtraction_error=0 if amount==0 else direct_error,fit=fit_info,residual_rows=residual_rows,seeds=[])
        r['trials'].append(trial)
        for seed in plan['residual_seeds']:
            cloud=invoke([args.residual_probe,residual_profile,raw/(name+'_'+str(seed)+'_cloud.wav'),plan['seconds'],1,1,seed])
            mixed=base+cloud
            errors=error(target,matrices(mixed[warm:]))
            max_power=max(abs(v) for row in errors for v in row['power_delta_db'])
            max_coherence=max(row['complex_coherence_error'] for row in errors)
            observed,_=measure(mixed[warm:warm+nref],measure_plan,16)
            concentration=np.array(observed['rows'][0]['concentration_LR'])
            reduction=base_concentration-concentration
            power_pass=max_power<plan['tolerances']['mixed_band_power_error_db']
            coherence_pass=max_coherence<plan['tolerances']['mixed_complex_coherence_error']
            density_pass=amount==0 or bool(np.all(reduction[4:]>=plan['tolerances']['minimum_high_concentration_reduction']))
            path=raw/(name+'_'+str(seed)+'_mix.wav');sf.write(path,mixed,48000,subtype='FLOAT')
            trial['seeds'].append(dict(seed=seed,power_errors=errors,maximum_power_error_db=max_power,
                maximum_complex_coherence_error=max_coherence,power_gate=power_pass,coherence_gate=coherence_pass,
                concentration_reduction_LR=reduction.tolist(),density_gate=density_pass,mixed_sha256=sha(path)))
            if seed==plan['review_seed']:
                review[name]=mixed;review['cloud_'+str(round(amount*100))]=cloud
        print(json.dumps(dict(amount=amount,seeds=[dict(seed=x['seed'],power_db=x['maximum_power_error_db'],
            density_gate=x['density_gate'],power_gate=x['power_gate']) for x in trial['seeds']])),flush=True)
    passed=all(seed[key] for trial in r['trials'] for seed in trial['seeds'] for key in ('power_gate','coherence_gate','density_gate'))
    r['technical_render_qualified']=passed
    if passed:
        r['review_files']=save_review(args.out,review,plan)
        target_page=page(args.workspace,args.out,plan)
        r['review_page']=str(target_page);r['review_page_sha256']=sha(target_page)
        shutil.copy2(target_page,args.out/'review.html')
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:index=list(csv.DictReader(f))
    assert len(index)==436
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    r.update(result='technical_pass_only' if passed else 'not_passed',c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        C_changes=False,default_models_changed=False,driver_changes=False,human_accepted=False,
        baseline_C_float_exact=True,low_frozen_stem_preserved=True,limits=[plan['scope'],
            'C stems are rendered independently then summed offline; this is not a new combined realtime host',
            'Nonnegative diagonal and coherence clipping do not guarantee exact full spectral-matrix restitution',
            'Mean power gates do not establish loudness equality, temporal naturalness or perceptual quality',
            'Fixed A is nearly dual-mono; this trial does not establish stereo widening or physical7.1.4',
            'Same-target training fit and procedural seeds are not independent-recording generalization'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],trials=len(r['trials']),review=r.get('review_page'))),flush=True)
