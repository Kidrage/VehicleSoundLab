"""Native fixed-idle short-time concentration; preserve every comparison and seed."""
import argparse,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from scipy.linalg import lstsq
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},observations=[],audio_exported=False,source_model_changed=False)


def moments(x):
    y=x-x.mean(axis=0);power=np.mean(y*y,axis=0)
    return dict(excess_kurtosis=(np.mean(y**4,axis=0)/power**2-3).tolist(),
        skew=(np.mean(y**3,axis=0)/power**1.5).tolist(),crest=(np.max(abs(y),axis=0)/np.sqrt(power)).tolist())


def observe(x,plan,folder):
    rate=plan['sample_rate'];trim=plan['trim_frames']
    sos=[signal.butter(4,band,btype='bandpass',fs=rate,output='sos') for band in plan['bands_hz']]
    filtered=np.column_stack([signal.sosfilt(s,x[:,0])[trim:-trim] for s in sos])
    result=dict(moments=moments(filtered),energy={})
    arrays=dict(audio=x,filtered=filtered,sos=np.array(sos))
    for frames in plan['energy_windows_frames']:
        n=len(filtered)//frames;tiles=filtered[:n*frames].reshape(n,frames,-1);power=np.mean(tiles*tiles,axis=1)
        centered=power-power.mean(axis=0);cov=centered.T@centered/n
        correlation=cov/np.sqrt(np.diag(cov)[:,None]*np.diag(cov)[None,:])
        cv=np.std(power,axis=0)/np.mean(power,axis=0)
        result['energy'][str(frames)]=dict(tiles=n,CV=cv.tolist(),max_over_mean=(power.max(axis=0)/power.mean(axis=0)).tolist(),correlation=correlation.tolist())
        arrays['energy_'+str(frames)]=power
        # Independent scalar sums, including off-diagonal relationships.
        scalar=np.array([[math.fsum(float(v)**2 for v in tiles[i,:,j])/frames for j in range(6)] for i in range(n)])
        assert np.max(abs(scalar-power))<1e-14
        for j in range(6):
            mean=math.fsum(filtered[:,j])/len(filtered);v=[float(t)-mean for t in filtered[:,j]]
            second=math.fsum(t*t for t in v)/len(v);fourth=math.fsum(t**4 for t in v)/len(v)
            assert abs(fourth/second**2-3-result['moments']['excess_kurtosis'][j])<1e-10
            for k in range(6):
                uj=math.fsum(power[:,j])/n;uk=math.fsum(power[:,k])/n
                top=math.fsum((float(row[j])-uj)*(float(row[k])-uk) for row in power)
                bot=math.sqrt(math.fsum((float(t)-uj)**2 for t in power[:,j])*math.fsum((float(t)-uk)**2 for t in power[:,k]))
                assert abs(top/bot-correlation[j,k])<1e-10
    np.savez_compressed(folder,**arrays)
    return result


try:
    plan_path=repo/'research/idle_microtexture_v1_plan.json';plan=load(plan_path)
    for path in [Path(__file__),plan_path,repo/'tools/research_archive_v1.py']:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    binary=np.tile([1.,-1.],24000)[:,None];assert moments(binary)['excess_kurtosis']==[-2.]
    sine=np.sin(2*np.pi*np.arange(48000)*113/48000)[:,None];assert abs(moments(sine)['excess_kurtosis'][0]+1.5)<1e-12
    assert np.max(abs(np.array(moments(sine)['excess_kurtosis'])-moments(sine*.13)['excess_kurtosis']))<1e-12
    parent=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1/F2_tailpipe'
    profile=load(parent/'profile.json');frequencies=np.array(profile['modal']['frequencies_hz'])
    paths={'F2_train':parent/'training.wav','F2_check':a.workspace/'references/analysis/idle_modal_v1/trial4/F2_holdout.wav'}
    for seed in plan['seeds']:
        for mode in ['000','050','100']:
            paths[f'candidate_{mode}_{seed}']=a.workspace/f'references/analysis/modal_texture_v1/trial1/mix_{mode}_{seed}.wav'
    n=plan['comparison_frames'];t=np.arange(n)/48000;angle=2*np.pi*t[:,None]*frequencies
    design=np.column_stack((np.cos(angle),np.sin(angle),np.ones(n)))
    references={}
    for name,path in paths.items():
        x,rate=sf.read(path,always_2d=True);assert rate==48000 and x.shape[1]==2 and len(x)>=n;x=x[:n]
        result=observe(x,plan,a.out/(name+'.npz'))
        row=dict(name=name,path=str(path),input_sha256=sha(path),whole=result)
        coefficients=lstsq(design,x,lapack_driver='gelsy')[0];residual=x-design@coefficients
        row['fixed_modal_remainder']=observe(residual,plan,a.out/(name+'_remainder.npz'))
        save(a.out/(name+'_coefficients.json'),coefficients.tolist());r['observations'].append(row)
        if name.startswith('F2_'):references[name]=x
        print(dict(name=name,kurtosis=result['moments']['excess_kurtosis'],CV10ms=result['energy']['480']['CV']),flush=True)
    for name,x in references.items():
        z=np.fft.rfft(x,axis=0)
        for seed in plan['seeds']:
            phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(z));phase[0]=phase[-1]=0
            shifted=np.fft.irfft(z*np.exp(1j*phase[:,None]),n=n,axis=0)
            assert np.max(abs(abs(np.fft.rfft(shifted,axis=0))-abs(z)))<1e-10
            tag=f'{name}_phase_{seed}';result=observe(shifted,plan,a.out/(tag+'.npz'))
            r['observations'].append(dict(name=tag,source=name,whole=result,interpretation='PSD-preserving observation control, not an engine candidate'))
    r.update(result='fixed_idle_short_time_concentration_observed',plan=plan,known_moments_and_independent_scalar_features_passed=True,
        runtime_changed=False,physical_source_or_mechanism_identified=False,all_seeds_retained=True,
        same_recording_check_not_independent=True,comparison_seconds=3,global_modal_subtraction_not_physical_separation=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],observations=len(r['observations'])),flush=True)
