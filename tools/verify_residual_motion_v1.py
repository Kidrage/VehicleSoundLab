"""Validate the actual C carrier bypass, stochastic energy and bounded pitch."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
parser.add_argument('--fit',required=True,type=Path)
parser.add_argument('--probe',required=True,type=Path)
parser.add_argument('--static-probe',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from residual_osc_v1.spectrum import matrices,error
from residual_motion_v1.features import powers,amplitudes,covariance

args.out.mkdir(parents=True,exist_ok=False)
fit=json.loads((args.fit/'report.json').read_text(encoding='utf-8'))
for name,digest in fit['source_sha256'].items():
    assert sha(args.fit/'exact_sources'/name)==digest,name
assert sha(args.fit/'A_moving.residual')==fit['static_model_sha256']
assert sha(args.fit/'A_moving.motion')==fit['motion_model_sha256']

def load(path,frames):
    x,rate=sf.read(path,always_2d=True)
    assert rate==48000 and x.shape==(frames,2) and np.isfinite(x).all()
    return x

def run(name,source,motion,seconds,pitch,amount,source_seed=8121907,motion_seed=230917):
    path=args.out/(name+'.wav');raw=args.out/(name+'_raw.wav');trace=args.out/(name+'.csv')
    command=[str(args.probe),str(source),str(motion),str(path),str(seconds),str(pitch),'1',str(amount),str(source_seed),str(motion_seed),str(raw),str(trace)]
    completed=subprocess.run(command,check=True,capture_output=True,timeout=120)
    x=load(path,round(seconds*48000));base=load(raw,round(seconds*48000))
    with trace.open(encoding='utf-8') as stream:records=list(csv.DictReader(stream))
    gains=np.array([[float(v) for k,v in row.items() if k.startswith('band')] for row in records])
    assert gains.min()>0 and gains.max()<1.76
    return x,base,gains,dict(name=name,command=command,stdout=completed.stdout.decode(),sha256=sha(path),raw_sha256=sha(raw),trace_sha256=sha(trace),
        peak=float(abs(x).max()),gain_range=[float(gains.min()),float(gains.max())])

source=args.fit/'A_moving.residual';motion=args.fit/'A_moving.motion'
renders=[];pitch_checks=[]
for pitch in (.9,1.,1.1):
    old=args.out/f'old_{pitch}.wav'
    subprocess.run([str(args.static_probe),str(source),str(old),'8',str(pitch),'1','8121907'],check=True,capture_output=True,timeout=120)
    old_audio=load(old,384000)
    for amount in (0,1):
        x,raw,gains,record=run(f'A_pitch{pitch}_amount{amount}',source,motion,8,pitch,amount)
        assert np.array_equal(raw,old_audio)
        if amount==0:assert np.array_equal(x,old_audio) and np.array_equal(gains,np.ones_like(gains))
        assert not np.array_equal(x[:192000],x[192000:])
        renders.append(record)
    pitch_checks.append(dict(pitch=pitch,frames=384000,zero_exact=True,raw_carriers_exact=True))
    print('A pitch',pitch,'zero/raw exact',flush=True)
x,raw,gains,record=run('A_amount_half',source,motion,8,1,.5);renders.append(record)
x,raw,gains,record=run('A_transition',source,motion,8,1,'rise-fall');renders.append(record)
with (args.out/'A_transition.csv').open() as stream:trace=list(csv.DictReader(stream))
amounts=np.array([float(row['amount']) for row in trace]);assert amounts[:200].max()==0
assert np.diff(amounts[200:600]).min()>=0 and np.diff(amounts[600:]).max()<=0

# Known stereo source, independent of the recording fit. Common band AM should
# keep its mean power/coherence while providing the specified envelope moments.
known_source=args.out/'known.residual';known_motion=args.out/'known.motion'
known_source.write_text('VSL_SOUND_RESIDUAL 1 48000 2 32\n1200 2400 .001 .002 .6 .2\n2400 6000 .002 .001 -.2 .3\n',encoding='ascii',newline='\n')
known_motion.write_text('VSL_RESIDUAL_MOTION 1 48000 480 2 2\n.6 .3\n1200 2400 .12 .04\n2400 6000 -.05 .1\n',encoding='ascii',newline='\n')
known=[];all_gains=[]
for source_seed,motion_seed in ((11031,5901),(62017,8303),(95179,17011)):
    x,raw,gains,record=run(f'known_{source_seed}',known_source,known_motion,16,1,1,source_seed,motion_seed)
    before=matrices(raw[24000:],bands=[(1200,2400),(2400,6000)])
    after=matrices(x[24000:],bands=[(1200,2400),(2400,6000)])
    comparison=error(before,after)
    assert max(abs(v) for row in comparison for v in row['power_delta_db'])<.5
    assert max(row['complex_coherence_error'] for row in comparison)<.04
    known.append(dict(**record,comparison=comparison));all_gains.append(gains)
g=np.concatenate(all_gains);mean_power=np.mean(g*g,axis=0);variance=np.var(g,axis=0)
basis=np.array([[.12,.04],[-.05,.1]]);expected_variance=np.sum(basis*basis,axis=1)/(1+np.sum(basis*basis,axis=1))
assert abs(mean_power-1).max()<.04
assert (abs(variance-expected_variance)/expected_variance).max()<.25

# Assess the real-context hypothesis with procedural seeds not used in fitting.
reference=load(args.fit/'reference.wav',fit['provenance']['reference_frames'])
base=load(args.fit/'accepted_pair.wav',384000)
_,reference_power=powers(reference);target_cov,_=covariance(amplitudes(reference_power))
assessment=[]
for source_seed,motion_seed in ((78283,13007),(41719,16001),(61927,19001)):
    x,raw,gains,record=run(f'heldout_{source_seed}',source,motion,8,1,1,source_seed,motion_seed)
    scores=[[],[]]
    for start in range(24000,len(x)-len(reference)+1,len(reference)):
        for k,candidate in enumerate((base+raw,base+x)):
            _,p=powers(candidate[start:start+len(reference)])
            c,_=covariance(amplitudes(p));scores[k].append(float(np.linalg.norm(c-target_cov)))
    assessment.append(dict(**record,mean_covariance_distance_static=float(np.mean(scores[0])),
        mean_covariance_distance_motion=float(np.mean(scores[1])),
        seed_held_out_from_fit=True,scope='Procedural seed holdout; same short real reference, not unseen recording validation'))
result=dict(schema='vsl.residual-motion-verification/1',result='pass',fit_sha256=sha(args.fit/'report.json'),
    pitch_checks=pitch_checks,renders=renders,known=known,real_context_assessment=assessment,
    expected_envelope_variance=expected_variance.tolist(),measured_envelope_variance=variance.tolist(),
    measured_envelope_mean_square=mean_power.tolist(),human_accepted=False,driving_attached=False,
    probe_sha256=sha(args.probe),static_probe_sha256=sha(args.static_probe),
    limits=['Variance assessment uses the same1.2s reference, not real held-out audio',
        'Negative covariance debt remains uncorrected; mean spectral debt is independently clipped',
        'Static and moving carriers retain fixed phases/frequencies; beating is not claimed eliminated',
        'No device/driver integration, long-run realtime or new timbre acceptance'])
paths=[Path(__file__),*sorted((repo/'modules/residual_motion').glob('*.[ch]')),
       *sorted((repo/'experiments/residual_motion_v1').glob('*.c')),
       repo/'tools/residual_motion_v1/features.py']
result['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in paths}
for p in paths:
    target=args.out/'exact_sources'/p.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
(args.out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result='pass',mean_square=mean_power.tolist(),variance=variance.tolist(),
    real_context=[(r['mean_covariance_distance_static'],r['mean_covariance_distance_motion']) for r in assessment]),ensure_ascii=False))
