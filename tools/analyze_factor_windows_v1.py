"""Check stationary/no-AM controls before interpreting the target's factor lags."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from factor_power_v1.windows import known,observe

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/factor_window_v1_plan.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
paths=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',repo/'tools/factor_power_v1/windows.py']
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.factor-window/1',result='running',source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),observations=[],input_sha256={})
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')

try:
    prior=args.workspace/'baselines/temporal_texture_v1'
    manifest=json.loads((prior/'manifest.json').read_text(encoding='utf-8'));entry={r['path']:r['sha256'] for r in manifest['files']}
    file='evidence/magnitude1/candidate_moments.npz';assert sha(prior/file)==entry[file]
    report['input_sha256'][str(prior/file)]=entry[file]
    archive=np.load(prior/file);model={k:archive[k] for k in ('rms','basis','rho','root','residual_rho')};phase=archive['fixed_phase']
    reference=args.workspace/'baselines/residual_motion_v1/evidence/fit1/reference.wav'
    ref,rate=sf.read(reference,always_2d=True);assert rate==48000
    ref_manifest=args.workspace/'baselines/residual_motion_v1/manifest.json'
    expected=next(r['sha256'] for r in json.loads(ref_manifest.read_text(encoding='utf-8'))['files'] if r['path']=='evidence/fit1/reference.wav')
    assert sha(reference)==expected;report['input_sha256'][str(reference)]=expected
    cases=known(model,phase,plan)+[('fixed_A_reference',ref,'Same short normalized A target; not known stationary or a physical isolated source')]
    for name,audio,scope in cases:
        rows=[];arrays={}
        for config in plan['windows']:
            for origin in plan['origins_frames']:
                row,centers,z,scores=observe(audio,model,plan,config,origin)
                assert row['direct_DFT_relative_error']<plan['tolerances']['direct_DFT_relative'],(name,row)
                if name=='known_stationary_OSC':
                    assert row['log_motion_db']<plan['tolerances']['constant_harmonic_log_motion_db'],row
                if name=='known_single_carrier_AM':
                    expected=.25*np.sin(2*np.pi*1.5*centers/48000)
                    observed=np.log(abs(z[:,4,0])/.2)
                    error=float(20/np.log(10)*np.sqrt(np.mean((expected-observed)**2)))
                    assert error<plan['tolerances']['known_AM_log_error_db'],(row,error)
                    row['known_AM_log_error_db']=error
                rows.append(row);key=config['name']+'_'+str(origin)
                arrays[key+'_centers']=centers;arrays[key+'_scores']=scores
        np.savez_compressed(args.out/(name+'.npz'),**arrays)
        report['observations'].append(dict(name=name,scope=scope,configurations=rows,
            score_npz_sha256=sha(args.out/(name+'.npz'))))
        print(json.dumps(dict(name=name,first_factor_lags=[dict(window=r['config'],origin=r['origin_frame'],
            variance=r['factors'][0]['variance'],lag1=r['factors'][0]['lags'][0]['ratio'],lag4=r['factors'][0]['lags'][1]['ratio'])
            for r in rows if r['origin_frame']==0])),flush=True)
    report.update(result='pass',runtime_changes=False,new_fit=False,human_accepted=False,limits=[plan['scope'],
        'Different windows change central-bin Gaussian-noise gain as well as leakage and smoothing; do not equate their variance or power',
        'No-AM controls may have band/window beating; this does not identify the real reference cause',
        'The single-carrier AM control validates sensitivity, not real multi-harmonic source separation'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=report['result'],observations=len(report['observations']))),flush=True)
