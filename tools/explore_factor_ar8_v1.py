"""Offline multi-lag amplitude factors; qualify stationary states before audio."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--analysis',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy.linalg import solve_discrete_lyapunov
from drive_evidence_v1.sources import sha
from harmonic_magnitude_v1.model import render as old_magnitude
from harmonic_magnitude_v1.legacy import parse,render as old_render
from magnitude_timescale_v1.statistics import magnitudes
from magnitude_timescale_v1.factors import fit,Factors,ar1_profiles
from magnitude_timescale_v1.render import render
from common_envelope_v1.features import band_power,analyze,summarize,scalar_power_check

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/factor_ar8_v1_plan.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
paths=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',
    repo/'tools/harmonic_magnitude_v1/model.py',repo/'tools/harmonic_magnitude_v1/legacy.py',
    repo/'tools/sustain_osc_v1/oracle.py',repo/'tools/common_envelope_v1/features.py',
    repo/'tools/magnitude_timescale_v1/statistics.py',repo/'tools/magnitude_timescale_v1/factors.py',
    repo/'tools/magnitude_timescale_v1/render.py']
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.factor-ar8-exploration/1',result='running',source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    timescale_report_sha256=sha(args.analysis/'report.json'),controls=[],trials=[])
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def companion(coefficients):
    size=len(coefficients);a=np.zeros((size,size));a[0]=coefficients
    if size>1:a[1:,:-1]=np.eye(size-1)
    return a


def covariance_check(profile):
    a=companion(profile['coefficients']);q=np.zeros_like(a);q[0,0]=profile['innovation_variance']
    actual=solve_discrete_lyapunov(a,q)
    error=float(np.max(abs(actual-profile['covariance'])))
    assert error<plan['tolerances']['stationary_covariance_equation_absolute'],error
    return error


def measure(audio):
    starts,power=band_power(audio,measurement)
    error=scalar_power_check(audio,starts,power,measurement)
    assert error<plan['tolerances']['direct_DFT_relative']
    return dict(summary=summarize(analyze(starts,power,len(audio),measurement)),
        direct_DFT_relative_error=error,mean_band_power_LR=power.mean(axis=0).tolist())


try:
    source=json.loads((args.analysis/'report.json').read_text(encoding='utf-8'));assert source['result']=='pass'
    for path,digest in source['input_sha256'].items():assert sha(path)==digest,path
    prior=args.workspace/'baselines/temporal_texture_v1'
    archive=np.load(prior/'evidence/magnitude1/candidate_moments.npz')
    model={k:archive[k] for k in ('rms','basis','rho','root','residual_rho')};phase,mask=archive['fixed_phase'],archive['mask']
    frozen=args.workspace/'baselines/residual_motion_v1/evidence/fit1'
    reference,rate=sf.read(frozen/'reference.wav',always_2d=True);assert rate==48000
    base,rate=sf.read(frozen/'accepted_pair.wav',always_2d=True);assert rate==48000
    _,z=magnitudes(reference)
    logs=np.log(np.maximum(abs(z),np.maximum(model['rms']*1e-6,1e-20)[None,:]))
    centered=(logs-logs.mean(axis=0)).reshape(len(z),-1)
    basis=model['basis'].transpose(1,0,2).reshape(len(model['rho']),-1)
    scores=centered@basis.T/np.sum(basis*basis,axis=1)[None,:]
    profiles,stats=fit(scores,plan['factor_order'])
    report['factors']=stats
    report['stationary_covariance_max_error']=max(covariance_check(p) for p in profiles)
    np.savez_compressed(args.out/'factor_profiles.npz',coefficients=np.array([p['coefficients'] for p in profiles]),
        covariance=np.array([p['covariance'] for p in profiles]),innovation_variance=np.array([p['innovation_variance'] for p in profiles]),
        conditional_cholesky=np.array([p['conditional_cholesky'] for p in profiles]))
    # Three known processes, independent of the recording, initialized using an
    # independent Lyapunov solver; verify actual Factors histories and samples.
    rng=np.random.default_rng(plan['known_control_seed'])
    for coefficients in (np.array([.8]),np.array([.93]),np.array([1.7,-.81])):
        a=companion(coefficients);q=np.zeros_like(a);q[0,0]=1
        c=solve_discrete_lyapunov(a,q);innovation=1/c[0,0];c/=c[0,0]
        p=dict(coefficients=coefficients,covariance=c,innovation_variance=innovation,
            conditional_cholesky=np.linalg.cholesky(c[1:,1:]-np.outer(c[1:,0],c[1:,0])))
        voice=Factors([p],rng.normal(size=1),rng)
        samples=np.empty(plan['known_control_observations']);samples[0]=voice.history[0,0]
        noise=rng.normal(size=len(samples)-1)
        for i in range(1,len(samples)):samples[i]=voice.advance(np.array([noise[i-1]]))[0]
        errors=[];values=[]
        for lag in plan['known_control_lags']:
            actual=float(samples[lag:]@samples[:len(samples)-lag]/(len(samples)-lag))
            expected=float((np.linalg.matrix_power(a,lag)@c)[0,0])
            errors.append(abs(actual-expected));values.append(dict(lag=lag,observed=actual,expected=expected))
        assert max(errors)<plan['tolerances']['known_covariance_absolute'],max(errors)
        report['controls'].append(dict(coefficients=coefficients.tolist(),maximum_covariance_error=max(errors),lags=values))
    # Exact compatibility path: AR1 factors and the same innovation stream.
    before=old_magnitude(model,phase,48000,78283,mask)
    after=render(model,ar1_profiles(model['rho']),phase,48000,78283,mask)
    parity=float(abs(before-after).max());assert parity<plan['tolerances']['AR1_render_parity_absolute'],parity
    report['AR1_render_parity_max_error']=parity
    measurement=json.loads((repo/'research/common_envelope_v1_plan.json').read_text(encoding='utf-8'))
    report['measurement_plan_sha256']=sha(repo/'research/common_envelope_v1_plan.json')
    measurement.update(block_seconds=[1],offset_fractions=[0],detrend_orders=[1]);warm=measurement['warmup_frames']
    report['reference']=measure(reference)
    profile=repo/'voices/dna_bank_v1/V10 Exterior.model'
    old,high,_=old_render(parse(profile),len(base),48271,mask)
    dna,rate=sf.read(args.workspace/'baselines/coherent_low_v1/evidence/raw/dna.wav',always_2d=True)
    error=float(abs(old-dna).max());assert error<plan['tolerances']['legacy_C_absolute']
    report['legacy_C_error']=error
    for seed in plan['procedural_seeds']:
        high_new=render(model,profiles,phase,len(base),seed,mask)
        candidate=base+(high_new-high)
        path=args.out/f'factor8_{seed}.wav';sf.write(path,candidate,48000,subtype='FLOAT')
        decoded,rate=sf.read(path,always_2d=True);assert rate==48000
        report['trials'].append(dict(seed=seed,path=path.name,sha256=sha(path),
            peak=float(abs(decoded).max()),measurement=measure(decoded[warm:])))
        print(json.dumps(dict(seed=seed,peak=report['trials'][-1]['peak'],
            slow_shape=report['trials'][-1]['measurement']['summary'][0]['medians']['slow_shape_rms_db_LR'])),flush=True)
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
    assert len(index)==436
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    report.update(result='pass',c_h_count=len(index),runtime_changes=False,model_bank_changes=False,human_accepted=False,
        qualification='offline experimental candidate only',limits=[plan['scope'],
        'Biased finite-block autocovariance and eight parameters per factor can absorb drift or window artifacts',
        'Stationary covariance checks do not demonstrate realism, physical modulation or held-out recording prediction',
        'Gaussian log amplitudes remain unbounded and same-run power can deviate from ensemble expectation',
        'No C implementation, UI/device change, state mapping or spatial-source claim'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=report['result'],trials=len(report['trials']),AR1_parity=report['AR1_render_parity_max_error'])))
