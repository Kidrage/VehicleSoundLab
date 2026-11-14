"""Direct native filters, normal equations and real-valued phase-shift audit."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','study','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[name]='2'
import numpy as np
import soundfile as sf
from scipy import linalg,signal
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',cases=[])


def zero_phase(sos,x):
    edge=3*(2*len(sos)+1-min(sum(sos[:,2]==0),sum(sos[:,5]==0)))
    x=np.concatenate([2*x[0]-x[edge:0:-1],x,2*x[-1]-x[-2:-edge-2:-1]])
    def causal(v):
        original=v[0].copy();scale=1.
        for row in sos:
            b=row[:3]/row[3];den=row[3:]/row[3];dc=b.sum()/den.sum()
            state=scale*np.array([dc-b[0],b[2]-den[2]*dc])[:,None]*original[None,:]
            v,_=signal.lfilter(b,den,v,axis=0,zi=state);scale*=dc
        return v
    return causal(causal(x)[::-1])[::-1][edge:-edge]


def coordinate(positions,start):
    times=start+np.arange(43200)/48000
    indices=np.flatnonzero((times>=positions[0])&(times<positions[13312]))
    at=np.searchsorted(positions,times[indices],side='right')-1
    phase=(at+(times[indices]-positions[at])/(positions[at+1]-positions[at]))/1024
    angles=2*np.pi*phase[:,None]*np.arange(1,289)[None,:]
    basis=np.column_stack([np.ones(len(phase)),np.cos(angles),np.sin(angles)])
    gram=basis.T@basis
    factor=linalg.cho_factor(gram)
    eig=linalg.eigvalsh(gram)
    assert min(eig)>0
    return indices,phase,basis,factor,float(max(eig)/min(eig))


def independent_features(values,phase,settings):
    features=[];DC=[];count=values.shape[1]
    for cycle in range(2,11):
        at=np.flatnonzero((phase>=cycle)&(phase<cycle+1))
        columns=[np.ones(len(at))]
        columns.extend(np.cos(2*np.pi*k*phase[at]) for k in range(1,5))
        columns.extend(np.sin(2*np.pi*k*phase[at]) for k in range(1,5))
        design=np.array(columns).T
        coef=linalg.solve(design.T@design,design.T@(values[at]**2).reshape(len(at),-1),assume_a='pos')
        coef=coef.reshape(9,count,2)
        DC.append(coef[0]);features.append((coef[1:5]-1j*coef[5:9]).transpose(1,2,0))
    level=np.mean(DC,axis=0)
    f=np.array(features).transpose(1,0,2,3)/np.maximum(level,settings['minimum_energy_FS2'])[:,None,:,None]
    f[np.max(level,axis=1)<settings['minimum_energy_FS2']]=0
    even=f[:,::2].mean(axis=1);odd=f[:,1::2].mean(axis=1)
    observed=np.mean(even.real*odd.real+even.imag*odd.imag,axis=(1,2))
    rng=np.random.default_rng(settings['seed']);null=[]
    for _ in range(settings['permutations']):
        angle=rng.uniform(0,2*np.pi,9)[:,None]*np.arange(1,5)[None,:]
        # Explicit real rotations instead of complex multiply/score helper.
        real=f.real*np.cos(angle)[None,:,None,:]+f.imag*np.sin(angle)[None,:,None,:]
        imag=f.imag*np.cos(angle)[None,:,None,:]-f.real*np.sin(angle)[None,:,None,:]
        e_real=real[:,::2].mean(axis=1);o_real=real[:,1::2].mean(axis=1)
        e_imag=imag[:,::2].mean(axis=1);o_imag=imag[:,1::2].mean(axis=1)
        null.append(float(max(np.mean(e_real*o_real+e_imag*o_imag,axis=(1,2)))))
    null=np.array(null);p=np.array([(1+sum(null>=v))/257 for v in observed])
    return f,np.array(DC),observed,null,p


try:
    shutil.copy2(Path(__file__),a.out/'audit_source.py')
    report=load(a.study/'report.json');plan=load(repo/'research/F3_native_power_v1_plan.json')
    assert report['result']=='native_time_relationship_measured'
    for name,want in report['sources'].items():assert sha(repo/name)==want,name
    for name,want in report['inputs'].items():assert sha(name)==want,name
    r['producer_report_sha256']=sha(a.study/'report.json')
    known_positions=.2+np.arange(14336)/(1024*67)
    known_coord=coordinate(known_positions,0)
    positions_path=a.workspace/'baselines/F3_lift_voice_v1/evidence/fit2/F3 Sixth Before Upshift/coordinates.npz'
    with np.load(positions_path) as f:positions=f['source_seconds'].copy()
    actual_coord=coordinate(positions,199.6)
    with np.load(a.study/'coordinate.npz') as f:
        assert np.array_equal(actual_coord[0],f['indices'])
        assert np.max(abs(actual_coord[1]-f['phase']))<2e-12
        assert np.array_equal(np.floor(actual_coord[1]).astype(int),f['cycle'])
    time=np.arange(43200)/48000;phase=(time-.2)*67
    rng=np.random.default_rng(1907);noise=rng.standard_normal((43200,2))*.04
    cases=[('known_stationary',noise,known_coord),('known_AM',noise*np.sqrt(1+.8*np.cos(2*np.pi*phase))[:,None],known_coord)]
    prior=a.workspace/'baselines/F3_warp_noise_v1/evidence/controls1'
    for seed in [1907,23117,61927,8121907]:
        with np.load(prior/f'seed{seed}/native.npz') as f:
            cases.extend([(f'seed{seed}_stationary',f['stationary'].copy(),actual_coord),
                          (f'seed{seed}_known_AM',f['modulated'].copy(),actual_coord)])
    source_path=a.workspace/'baselines/F3_lift_voice_v1/evidence/fit2/F3 Sixth Before Upshift/native.wav'
    source,rate=sf.read(source_path,always_2d=True);assert rate==48000
    with np.load(a.study/'source_native.npz') as f:assert np.array_equal(source,f['audio'])
    cases.append(('source',source,actual_coord))
    largest=dict(filter_FS=0.,projection_FS=0.,features=0.,DC_FS2=0.,score=0.,null=0.)
    for name,audio,coord in cases:
        indices,phase,basis,factor,condition=coord
        columns=[]
        for lo,hi in plan['bands_hz']:
            sos=signal.butter(4,[lo,hi],fs=48000,btype='bandpass',output='sos')
            columns.append(zero_phase(sos,audio)[indices])
        full=np.array(columns).transpose(1,0,2)
        with np.load(a.study/name/'arrays.npz') as f:saved={k:f[k].copy() for k in f.files}
        error=float(np.max(abs(full-saved['full'])));assert error<2e-12
        largest['filter_FS']=max(largest['filter_FS'],error)
        coefficients=linalg.cho_solve(factor,basis.T@full.reshape(len(full),-1))
        coherent=(basis@coefficients).reshape(full.shape);residual=full-coherent
        error=max(float(np.max(abs(coherent-saved['coherent']))),float(np.max(abs(residual-saved['residual']))))
        assert error<2e-10;largest['projection_FS']=max(largest['projection_FS'],error)
        assert np.max(abs(full-coherent-residual))<1e-16
        assert np.max(abs(basis.T@residual.reshape(len(full),-1)))/len(full)<1e-12
        target=load(a.study/name/'result.json');result=dict(name=name,design_condition=condition,routes={})
        for route,values in [('full',full),('residual',residual)]:
            features,dc,observed,null,p=independent_features(values,phase,plan['cyclic'])
            error=float(np.max(abs(features-saved[route+'_features'])));assert error<1e-8
            largest['features']=max(largest['features'],error)
            error=float(np.max(abs(dc-saved[route+'_cycle_DC'])));assert error<1e-12
            largest['DC_FS2']=max(largest['DC_FS2'],error)
            error=float(np.max(abs(observed-[v['train_heldout_cross_statistic'] for v in target[route]['bands']])));assert error<1e-8
            largest['score']=max(largest['score'],error)
            error=float(np.max(abs(null-target[route]['max_null'])));assert error<1e-8
            largest['null']=max(largest['null'],error)
            assert np.array_equal(p,[v['familywise_p'] for v in target[route]['bands']])
            supported=[band for band,value,prob in zip(plan['bands_hz'],observed,p) if value>0 and prob<=.01]
            result['routes'][route]=dict(supported=supported,p=p.tolist())
        r['cases'].append(result);print(dict(name=name,verified=True),flush=True)
    parent=a.workspace/'baselines/F3_lift_voice_v1'
    with (parent/'source/handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==647 and all(sha(repo/v['文件'])==v['SHA-256'] for v in rows)
    voices=load(parent/'inputs/voice_files_sha256.json')
    assert len(voices)==74 and all(sha(repo/n)==h for n,h in voices.items())
    r.update(result='native_time_independent_audit_passed',maximum_errors=largest,C_H_exact=647,voice_files_exact=74,
        known_AM_actual_primary_detected=sum(bool(v['routes']['residual']['supported']) for v in r['cases'] if v['name'].startswith('seed') and v['name'].endswith('_known_AM')),
        primary_source_supported=r['cases'][-1]['routes']['residual']['supported'],
        native_source_waveform_exact=True,cyclic_law_qualified=False,hearing_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r['maximum_errors'])
