"""Independent excess statistics, PRNG/AR, complex OSC and FFT-convolution replay."""
import argparse,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from scipy.fft import next_fast_len
from research_archive_v1 import load,save,sha


def normals(seed,count):
    mask=(1<<64)-1;state=seed or 1;out=[]
    def uniform():
        nonlocal state
        state^=state>>12;state^=(state<<25)&mask;state^=state>>27;state&=mask
        return (((state*2685821657736338717)&mask)>>11)+.5
    while len(out)<count:
        radius=math.sqrt(-2*math.log(uniform()/2**53));angle=2*math.pi*uniform()/2**53
        out.extend((radius*math.cos(angle),radius*math.sin(angle)))
    return np.asarray(out[:count])


def statistics(energy):
    values=np.array([[.5*math.log(float(v)) for v in row] for row in energy])
    values-=np.array([math.fsum(values[:,k])/len(values) for k in range(values.shape[1])])
    dim=values.shape[1];n=len(values)
    cov=np.array([[math.fsum(values[:,i]*values[:,j])/n for j in range(dim)] for i in range(dim)])
    lag=np.array([[math.fsum(values[:-1,i]*values[1:,j])/(n-1) for j in range(dim)] for i in range(dim)])
    return cov,lag


def concentration(audio):
    trimmed=[]
    for band in [[1200,2200],[2200,4000],[4000,8000],[8000,14000]]:
        y=signal.sosfilt(signal.butter(4,band,btype='bandpass',fs=48000,output='sos'),audio[:144000,0])[4800:-4800]
        power=np.mean(y*y);energy=np.mean(y[:len(y)//480*480].reshape(-1,480)**2,axis=1)
        trimmed.append(dict(band_hz=band,excess_kurtosis=float(np.mean((y-y.mean())**4)/np.mean((y-y.mean())**2)**2-3),
            energy_CV_10ms=float(np.std(energy)/np.mean(energy))))
    return trimmed


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
r=dict(result='running',renders=[],maximum_FLOAT_error=0.,maximum_state_error=0.)
try:
    report=load(a.input/'report.json');recipe=report['recipe'];profile=load(a.input/'profile.json');model=profile['envelope']
    for name,h in report['sources'].items():assert sha(a.input/'exact_sources'/name)==h
    obs=a.workspace/recipe['observation'];assert sha(obs/'report.json')==report['observation_report_sha256']
    indices=profile['kernel_indices'];key='energy_480'
    cov,lag=statistics(np.load(obs/'F2_train.npz')[key][:,indices])
    checks=[statistics(np.load(obs/f'F2_train_phase_{seed}.npz')[key][:,indices]) for seed in recipe['seeds']]
    C=cov-sum(row[0] for row in checks)/3;lag-=sum(row[1] for row in checks)/3
    assert abs(C-np.array(model['covariance'])).max()<1e-12
    L=np.array(model['factor']);assert abs(L@L.T-C).max()<1e-12 and np.linalg.eigvalsh(C).min()>0
    alpha=max(0.,min(.98,float(np.trace(lag)/np.trace(C))));assert abs(alpha-model['alpha'])<1e-12
    basepath=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1/F2_tailpipe/profile.json'
    assert sha(basepath)==report['parent_profile_sha256'];base=load(basepath);frames=recipe['seconds']*48000
    t=np.arange(frames)/48000;core=np.zeros((frames,2));modal=base['modal']
    for f,amp,phase in zip(modal['frequencies_hz'],modal['amplitude_LR'],modal['initial_phase_LR']):
        core+=(np.exp(2j*np.pi*np.remainder(t*f,1.))[:,None]*(np.array(amp)*np.exp(1j*np.array(phase)))).real
    u=(1-np.cos(np.pi*(np.arange(frames)%480)/480))/2;at=np.arange(frames)//480
    variance=(1-u)**2+u*u+2*alpha*u*(1-u)
    for seed in recipe['seeds']:
        saved=np.load(a.input/f'states_{seed}.npz');normal=normals(seed^0x8CB92BA72F3D8DD7,saved['normal'].size).reshape(saved['normal'].shape)
        assert np.array_equal(normal,saved['normal']);state=np.empty_like(normal)
        for i,z in enumerate(normal):
            innovation=np.array([math.fsum(row*z) for row in L])
            state[i]=innovation if i==0 else alpha*state[i-1]+math.sqrt(1-alpha*alpha)*innovation
        err=float(abs(state-saved['state']).max());assert err<1e-12;r['maximum_state_error']=max(r['maximum_state_error'],err)
        value=((1-u[:,None])*state[at]+u[:,None]*state[at+1])/np.sqrt(variance[:,None])
        streams=[];count=frames+base['warmup_frames']
        for k,kernel in enumerate(base['kernels']):
            noise=normals(seed^(0x9E3779B97F4A7C15*(k+1)&((1<<64)-1)),count)
            h=np.array(kernel['taps']);size=next_fast_len(len(noise)+len(h)-1)
            y=np.fft.irfft(np.fft.rfft(noise,size)*np.fft.rfft(h,size),size)[base['warmup_frames']:count]*kernel['gain']
            streams.append(y[:,None]*np.array([[1.,kernel['right_over_left']]]))
        actual_core,_=sf.read(a.input/f'core_{seed}.wav',always_2d=True);assert abs(actual_core-core).max()<3e-8
        for amount in recipe['amounts']:
            gain=np.exp(amount*value-amount*amount*np.diag(C));detail=np.zeros_like(core)
            for k,stream in enumerate(streams):detail+=stream*(gain[:,indices.index(k),None] if k in indices else 1.)
            label=f'{round(amount*100):03d}_{seed}';mix,_=sf.read(a.input/f'mix_{label}.wav',always_2d=True)
            actual_detail,_=sf.read(a.input/f'detail_{label}.wav',always_2d=True)
            err=max(float(abs(core+detail-mix).max()),float(abs(detail-actual_detail).max()));assert err<3e-8
            r['maximum_FLOAT_error']=max(r['maximum_FLOAT_error'],err)
            if amount==0:
                frozen,_=sf.read(a.workspace/f'baselines/idle_texture_v2/evidence/trial1/fine_{seed}.wav',always_2d=True)
                assert np.array_equal(mix,frozen)
            r['renders'].append(dict(seed=seed,amount=amount,FLOAT_error=err,concentration=concentration(mix)))
        print(dict(seed=seed,replayed=True),flush=True)
    r.update(result='train_only_statistics_and_all9_fast_detail_renders_verified',training_only=True,zero_FLOAT_exact=True,
        input_report_sha256=sha(a.input/'report.json'),physical_modulation_identified=False,listening_acceptance=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],maximum_FLOAT_error=r['maximum_FLOAT_error']),flush=True)
