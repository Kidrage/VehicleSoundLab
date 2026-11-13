"""Independent replay and spectral observations; never a naturalness test."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import ndimage,signal
from drive_evidence_v1.sources import sha
from sustain_osc_v1.oracle import Gaussian

def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def spectral_shape(x,reference):
    f,p=signal.welch(x[:,0],fs=48000,nperseg=24000,noverlap=12000,detrend=False)
    _,q=signal.welch(reference[:,0],fs=48000,nperseg=24000,noverlap=12000,detrend=False)
    p=ndimage.gaussian_filter1d(p,4);q=ndimage.gaussian_filter1d(q,4)
    rows=[]
    for lo,hi in [[120,400],[400,1200],[1200,2200],[2200,4000],[4000,8000],[8000,14000]]:
        use=(f>=lo)&(f<hi);err=10*np.log10(np.maximum(p[use],1e-30)/np.maximum(q[use],1e-30))
        rows.append(dict(band_hz=[lo,hi],log_spectral_RMS_error_db=float(np.sqrt(np.mean(err*err)))))
    return rows

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',checks=[],comparisons=[])
try:
    shutil.copy2(__file__,a.out/'executed_audit.py')
    profile=load(a.input/'profile.json');report=load(a.input/'report.json');plan=report['plan']
    assert profile['modal']==load(a.workspace/'references/analysis/idle_modal_v1/trial4/profile.json')['modal']
    assert not profile['recorded_trajectory'] and not profile['room']
    covariance=np.array(profile['envelope']['covariance']);eig=np.linalg.eigvalsh(covariance)
    assert eig.min()>0 and 0<=profile['envelope']['alpha']<=.98
    # Independently integrate exact finite FIR responses.
    n=plan['spectral_grid_frames'];f=np.fft.fftfreq(n,1/48000);matrix=[]
    for model in profile['kernels']:
        h=np.array(model['taps']);assert len(h)==8192
        power=abs(np.fft.fft(h,n))**2/n
        assert abs(power.sum()-np.dot(h,h))<1e-12 and abs(np.dot(h,h)-1)<1e-12
        matrix.append([float(power[(abs(f)>=lo)&(abs(f)<hi)].sum()) for lo,hi in plan['energy_bands_hz']])
    assert np.max(abs(np.array(matrix).T-np.array(report['budget']['response_matrix'])))<1e-12
    frames=plan['seconds']*48000;t=np.arange(frames)/48000
    main=np.zeros((frames,2))
    for f,amp,phase in zip(profile['modal']['frequencies_hz'],profile['modal']['amplitude_LR'],profile['modal']['initial_phase_LR']):
        main+=np.array(amp)*np.cos(2*np.pi*f*t[:,None]+np.array(phase))
    parent=a.workspace/'references/analysis/idle_modal_v1/trial4'
    train,_=sf.read(parent/'F2_training.wav',always_2d=True);held,_=sf.read(parent/'F2_holdout.wav',always_2d=True)
    for seed in plan['seeds']:
        saved=np.load(a.input/f'states_{seed}.npz');state=saved['states'];normal=saved['normal']
        cov=np.asarray(profile['envelope']['covariance']);l=np.linalg.cholesky(cov)
        alpha=profile['envelope']['alpha'];s=profile['envelope']['strength'];hop=profile['envelope']['hop_frames']
        rng=Gaussian(seed^0xD1B54A32D192ED03)
        z=np.array([rng.next() for _ in range(normal.size)]).reshape(normal.shape)
        assert np.array_equal(z,normal)
        previous=l@z[0];state_error=float(abs(previous-state[0]).max())
        for j in range(1,len(state)):
            previous=alpha*previous+np.sqrt(1-alpha*alpha)*(l@z[j])
            state_error=max(state_error,float(abs(previous-state[j]).max()))
        assert state_error<1e-14
        static=np.zeros_like(main);dynamic=static.copy();direct_error=0.
        for i,model in enumerate(profile['kernels']):
            rng=Gaussian(seed^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1)))
            count=frames+plan['warmup_frames']
            noise=np.fromiter((rng.next() for _ in range(count)),dtype=float,count=count)
            h=np.array(model['taps'])
            # Different convolution implementation, plus literal FIR sums at separated samples.
            y=signal.fftconvolve(noise,h)[plan['warmup_frames']:count]*model['gain']
            for j in [0,1,959,960,8191,20003,frames-1]:
                at=plan['warmup_frames']+j
                literal=sum(float(h[k])*float(noise[at-k]) for k in range(len(h)))*model['gain']
                direct_error=max(direct_error,abs(literal-y[j]))
            gain=np.empty(frames)
            for j in range(len(state)-1):
                start=j*hop;stop=min(frames,start+hop)
                if start>=frames:break
                u=(1-np.cos(np.pi*np.arange(stop-start)/hop))/2
                variance=cov[i,i]*((1-u)**2+u*u+2*alpha*u*(1-u))
                gain[start:stop]=np.exp(s*((1-u)*state[j,i]+u*state[j+1,i])-s*s*variance)
            stereo=y[:,None]*np.array([1.,model['right_over_left']])
            static+=stereo;dynamic+=stereo*gain[:,None]
        errors={}
        for method,texture in [('fine',static),('dynamic',dynamic)]:
            actual,rate=sf.read(a.input/f'{method}_{seed}.wav',always_2d=True)
            actual_detail,rd=sf.read(a.input/f'{method}_detail_{seed}.wav',always_2d=True)
            assert rate==rd==48000 and len(actual)==frames
            error=float(abs(actual-(main+texture)).max())
            de=float(abs(actual_detail-texture).max())
            assert error<3e-8 and de<3e-8 and np.isfinite(actual).all() and abs(actual).max()<1
            errors[method]=dict(mix_maximum_error=error,detail_maximum_error=de)
            r['comparisons'].append(dict(seed=seed,method=method,
                training_fine_spectrum=spectral_shape(actual,train),holdout_fine_spectrum=spectral_shape(actual,held)))
        old,_=sf.read(parent/f'mix_{seed}.wav',always_2d=True)
        r['comparisons'].append(dict(seed=seed,method='original',training_fine_spectrum=spectral_shape(old,train),
            holdout_fine_spectrum=spectral_shape(old,held)))
        assert direct_error<1e-12
        r['checks'].append(dict(seed=seed,scalar_recurrence_error=state_error,direct_FIR_error=direct_error,replay=errors))
        print(json.dumps(dict(stage='independently_replayed',seed=seed,errors=errors)),flush=True)
    r.update(result='three_seeds_fir_and_envelope_replay_verified',profile_sha256=sha(a.input/'profile.json'),
        covariance_eigenvalues=eig.tolist(),old_modal_unchanged=True,scope='Numerical replay and spectral observations only; no listening acceptance.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
