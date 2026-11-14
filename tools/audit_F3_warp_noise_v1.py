"""Independent direct FIR/polyphase and power-demodulation audit; no source audio."""
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
from scipy import signal
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',cases=[])


def independent_map(audio,start,positions,cutoff):
    first=int(np.floor((positions[0]-start)*48000+1e-6))-4800
    stop=int(np.ceil((positions[-1]-start)*48000-1e-6))+4801
    assert 0<=first<stop<=len(audio)
    n=np.arange(-512,513);kernel=2*cutoff/48000*np.sinc(2*cutoff/48000*n)*np.kaiser(1025,12)
    kernel/=kernel.sum()
    filtered=np.column_stack([np.convolve(audio[first:stop,c],kernel,'same') for c in (0,1)])
    # Direct evaluation of the two neighboring upsampled values. SciPy's
    # 16x filter is a321tap Kaiser sinc; the retained query support is interior.
    n=np.arange(-160,161);poly=np.sinc(n/16)/16*np.kaiser(321,8.6)
    poly*=16/poly.sum()
    at=(positions-start-first/48000)*48000*16
    lower=np.floor(at).astype(int);fraction=at-lower
    def evaluate(index):
        k=(index[:,None]+160)//16-np.arange(21)[None,:]
        taps=index[:,None]+160-16*k;keep=(taps>=0)&(taps<len(poly))
        assert k.min()>=0 and k.max()<len(filtered)
        weights=poly[np.clip(taps,0,len(poly)-1)]*keep
        return np.sum(filtered[k]*weights[:,:,None],axis=1)
    return evaluate(lower)*(1-fraction[:,None])+evaluate(lower+1)*fraction[:,None]


def independent_zero_phase(sos,audio):
    # Derive per-section steady DC states, then use separate scalar lfilter
    # passes, rather than producer sosfiltfilt. Odd endpoint extension is explicit.
    edge=3*(2*len(sos)+1-min(sum(sos[:,2]==0),sum(sos[:,5]==0)))
    extended=np.concatenate([2*audio[0]-audio[edge:0:-1],audio,
                             2*audio[-1]-audio[-2:-edge-2:-1]])
    def causal(values):
        initial=values[0].copy();out=values;scale=1.
        for section in sos:
            b=section[:3]/section[3];den=section[3:]/section[3]
            gain=b.sum()/den.sum()
            steady=scale*np.array([gain-b[0],b[2]-den[2]*gain])
            out,_=signal.lfilter(b,den,out,axis=0,zi=steady[:,None]*initial[None,:])
            scale*=gain
        return out
    return causal(causal(extended)[::-1])[::-1][edge:-edge]


def independent_dependence(audio,root,bands,plan):
    cycle=plan['cycle_frames'];count=len(audio)//cycle;trim=plan['trim_cycles']
    theta=2*np.pi*np.arange(cycle)/cycle;orders=np.arange(1,plan['harmonics']+1)
    features=[];levels=[]
    for lo,hi in bands:
        scale=48000/cycle/root
        sos=signal.butter(plan['filter_order'],[lo*scale,hi*scale],fs=48000,btype='bandpass',output='sos')
        filtered=independent_zero_phase(sos,audio)
        powers=filtered.reshape(count,cycle,2)[trim:count-trim]**2
        level=powers.mean(axis=(0,1));levels.append(level)
        beta=np.empty((len(powers),2,len(orders)),dtype=complex)
        for n in range(len(powers)):
            for channel in range(2):
                for k,order in enumerate(orders):
                    beta[n,channel,k]=2/cycle*(np.dot(powers[n,:,channel],np.cos(order*theta))-
                        1j*np.dot(powers[n,:,channel],np.sin(order*theta)))/max(level[channel],plan['minimum_energy_FS2'])
        if max(level)<plan['minimum_energy_FS2']:beta[:]=0
        features.append(beta)
    features=np.array(features)
    def score(f):
        even=f[:,0::2].mean(axis=1);odd=f[:,1::2].mean(axis=1)
        return (even.real*odd.real+even.imag*odd.imag).mean(axis=(1,2))
    observed=score(features);null=[];rng=np.random.default_rng(plan['seed'])
    for _ in range(plan['permutations']):
        phase=rng.uniform(0,2*np.pi,features.shape[1])
        angle=phase[:,None]*orders[None,:]
        factor=np.cos(angle)-1j*np.sin(angle)
        null.append(float(max(score(features*factor[None,:,None,:]))))
    null=np.array(null)
    prob=np.array([(1+sum(null>=value))/(len(null)+1) for value in observed])
    return np.array(levels),features,observed,null,prob


try:
    shutil.copy2(Path(__file__),a.out/'audit_source.py')
    plan=load(repo/'research/F3_warp_noise_v1_plan.json')
    analysis=load(repo/'research/F3_detail_v1_plan.json');report=load(a.study/'report.json')
    assert report['result']=='paired_frozen_map_controls_completed'
    for name,want in report['sources'].items():assert sha(repo/name)==want,name
    for name,want in report['inputs'].items():assert sha(name)==want,name
    r['producer_report_sha256']=sha(a.study/'report.json')
    with np.load(a.study/'coordinates.npz') as f:coords={k:f[k].copy() for k in f.files}
    parent=a.workspace/'baselines/F3_lift_voice_v1'
    with np.load(parent/'evidence/fit2/F3 Sixth Before Upshift/coordinates.npz') as f:
        assert np.array_equal(coords['actual'],f['source_seconds'])
    assert coords['affine'][0]==coords['actual'][0] and coords['affine'][-1]==coords['actual'][-1]
    assert np.array_equal(coords['affine'],np.linspace(coords['actual'][0],coords['actual'][-1],14336))
    start,stop=plan['native_context']['seconds'];rate=plan['native_context']['rate']
    frames=round((stop-start)*rate);assert frames==43200
    native_time=start+np.arange(frames)/rate;assert np.array_equal(coords['native_times'],native_time)
    # Explicit piecewise inverse and the declared endpoint extension.
    interval=np.searchsorted(coords['actual'],native_time,side='right')-1
    interval=np.clip(interval,0,14334)
    phase=(interval+(native_time-coords['actual'][interval])/
           (coords['actual'][interval+1]-coords['actual'][interval]))/1024
    assert np.max(abs(phase-coords['known_AM_cycles']))<2e-12
    largest=dict(mapped_FS=0.,power_FS2=0.,score=0.,null=0.)
    for seed in plan['noise_seeds']:
        folder=a.study/f'seed{seed}'
        with np.load(folder/'native.npz') as f:native=f['stationary'].copy();mod=f['modulated'].copy()
        rng=np.random.default_rng(seed);delay=plan['delay_frames']
        left=rng.standard_normal(frames+delay);other=rng.standard_normal(frames)
        rho=plan['right_delayed_left_fraction'];sigma=plan['noise_sigma']
        expected=sigma*np.stack([left[delay:],rho*left[:-delay]+np.sqrt(1-rho**2)*other],axis=1)
        assert np.array_equal(native,expected)
        assert np.array_equal(mod,native*np.sqrt(1+plan['AM_depth']*np.cos(2*np.pi*coords['known_AM_cycles']))[:,None])
        direct={
            'direct_canonical':native[:14336],
            'same_endpoints_affine_map':independent_map(native,start,coords['affine'],report['cutoff_hz']),
            'actual_frozen_map':independent_map(native,start,coords['actual'],report['cutoff_hz']),
            'known_AM_actual_frozen_map':independent_map(mod,start,coords['actual'],report['cutoff_hz'])}
        for route,wave in direct.items():
            with np.load(folder/(route+'.npz')) as f:arrays={k:f[k].copy() for k in f.files}
            error=float(np.max(abs(wave-arrays['canonical'])));assert error<2e-12
            largest['mapped_FS']=max(largest['mapped_FS'],error)
            blocks=arrays['canonical'].reshape(14,1024,2)
            mean=np.zeros((1024,2))
            for block in blocks:mean+=block
            mean/=14
            assert np.array_equal(arrays['coherent'],np.concatenate([mean]*14))
            assert np.array_equal(arrays['residual'],arrays['canonical']-arrays['coherent'])
            assert np.max(abs(np.mean(arrays['residual'].reshape(14,1024,2),axis=0)))<1e-16
            row=next(v for v in report['cases'] if v['seed']==seed and v['route']==route)
            powers,features,observed,null,prob=independent_dependence(arrays['residual'],report['root_hz'],analysis['bands_hz'],analysis['cyclic'])
            wanted=row['dependence'];wanted_power=np.array([v['power_LR'] for v in wanted['bands']])
            error=float(np.max(abs(powers-wanted_power)));assert error<1e-14
            largest['power_FS2']=max(largest['power_FS2'],error)
            error=float(np.max(abs(observed-[v['train_heldout_cross_statistic'] for v in wanted['bands']])));assert error<1e-9
            largest['score']=max(largest['score'],error)
            error=float(np.max(abs(null-wanted['max_null'])));assert error<1e-9
            largest['null']=max(largest['null'],error)
            assert np.array_equal(prob,[v['familywise_p'] for v in wanted['bands']])
            support=[band for band,value,pvalue in zip(analysis['bands_hz'],observed,prob)
                     if value>0 and pvalue<=analysis['cyclic']['familywise_p']]
            assert support==row['supported_bands']
            np.savez_compressed(a.out/(f'seed{seed}_{route}.npz'),features=features,power=powers,observed=observed,max_null=null,p=prob)
            r['cases'].append(dict(seed=seed,route=route,supported=support,mapped_max_FS=float(np.max(abs(wave-arrays['canonical'])))))
        print(dict(seed=seed,verified_routes=len(direct)),flush=True)
    old=parent/'source/handoff/C文件索引.csv'
    with old.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    assert len(rows)==647
    for row in rows:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    voices=load(parent/'inputs/voice_files_sha256.json');assert len(voices)==74
    for name,want in voices.items():assert sha(repo/name)==want,name
    r.update(result='independent_frozen_map_audit_passed',maximum_errors=largest,
        C_H_exact=len(rows),voice_files_exact=len(voices),source_audio_read=False,
        full_phase_extractor_qualified=False,physical_mechanical_origin_proven=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r['maximum_errors'])
