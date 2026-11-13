"""Independent QR/energy/complex-sum/FFT replay of conditional amplitude study."""
import argparse,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','evidence','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal,linalg
from scipy.fft import next_fast_len
from research_archive_v1 import load,save,sha


def normals(seed,count):
    mask=(1<<64)-1;state=seed or 1;out=[]
    def uniform():
        nonlocal state
        state^=state>>12;state^=(state<<25)&mask;state^=state>>27;state&=mask
        return ((((state*2685821657736338717)&mask)>>11)+.5)/2**53
    while len(out)<count:
        radius=math.sqrt(-2*math.log(uniform()));angle=2*math.pi*uniform()
        out.extend((radius*math.cos(angle),radius*math.sin(angle)))
    return np.asarray(out[:count])


def verify_model(model,feature,power):
    mean=np.array([math.fsum(power[:,j])/len(power) for j in range(4)])
    assert abs(mean-model['reference_power']).max()<1e-18
    design=np.column_stack((np.ones(len(feature)),feature))
    coefficient=linalg.lstsq(design,power/mean,lapack_driver='gelsy')[0]
    error=float(abs(coefficient-model['coefficients']).max());assert error<1e-12
    lower=np.array([coefficient[0,j]-math.fsum(math.hypot(coefficient[k+1,j],coefficient[k+4,j]) for k in range(3)) for j in range(4)])
    assert abs(lower-model['lower_power_bound']).max()<1e-12
    assert bool(np.all(lower>0))==model['positive']
    return error


def verify_assessment(model,f,e,expected):
    b=np.asarray(model['coefficients']);target=e/np.asarray(model['reference_power'])
    prediction=b[0]+sum(f[:,k,None]*b[k+1] for k in range(6))
    mse=np.array([math.fsum((target[:,j]-prediction[:,j])**2)/len(f) for j in range(4)])
    before=np.array([math.fsum((target[:,j]-b[0,j])**2)/len(f) for j in range(4)])
    assert abs(mse-expected['conditional_mse']).max()<1e-12
    assert abs(before-expected['constant_mse']).max()<1e-12
    assert abs(1-mse/before-expected['relative_mse_improvement']).max()<1e-12
    for j in range(4):
        u=target[:,j]-target[:,j].mean();v=prediction[:,j]-prediction[:,j].mean()
        correlation=math.fsum(u*v)/math.sqrt(math.fsum(u*u)*math.fsum(v*v))
        assert abs(correlation-expected['correlation'][j])<1e-12


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
r=dict(result='running',maximum_coefficient_error=0.,maximum_FLOAT_error=0.,renders=[])
try:
    obs=a.evidence/'observe1';trial=a.evidence/'trial1';observed=load(obs/'report.json');rendered=load(trial/'report.json')
    assert observed['candidate_gate'] and rendered['result']=='conditioned_detail_candidates_pending_listening'
    for folder,report in [(obs,observed),(trial,rendered)]:
        for name,h in report['sources'].items():assert sha(folder/'exact_sources'/name)==h
    model=load(trial/'model.json');assert sha(trial/'model.json')==sha(obs/'model.json')
    arrays={}
    for part in ['train','check']:
        saved=np.load(obs/(part+'.npz'));x=saved['audio'];frequencies=observed['frequencies_hz'];phase=[]
        row=next(v for v in observed['observations'] if v['name']==part)
        actual,rate=sf.read(row['input_path'],always_2d=True);assert rate==48000 and np.array_equal(x,actual)
        assert sha(row['input_path'])==row['input_sha256']
        # Explicit analytic DFT multiplier rather than scipy Hilbert.
        multiplier=np.zeros(len(x));multiplier[0]=multiplier[len(x)//2]=1;multiplier[1:len(x)//2]=2
        for frequency in frequencies:
            y=signal.sosfiltfilt(signal.butter(4,[frequency-10,frequency+10],btype='bandpass',fs=48000,output='sos'),x[:,0])
            z=np.fft.ifft(np.fft.fft(y)*multiplier);phase.append(z/abs(z))
        phase=np.asarray(phase).T;assert abs(phase-saved['phasors']).max()<1e-9
        native=np.column_stack((phase.real,phase.imag))[12000:-12000]
        f=np.array([[math.fsum(native[i:i+48,k])/48 for k in range(6)] for i in range(0,len(native),48)])
        e=[]
        for band in observed['plan']['detail_bands_hz']:
            y=signal.sosfilt(signal.butter(4,band,btype='bandpass',fs=48000,output='sos'),x[:,0])[12000:-12000]
            e.append([math.fsum(y[i:i+48]**2)/48 for i in range(0,len(y),48)])
        e=np.asarray(e).T
        assert abs(f-saved['feature']).max()<1e-9 and abs(e-saved['power']).max()<1e-16
        arrays[part]=(saved['feature'],saved['power'])
        verify_assessment(model,*arrays[part],observed['real'][part])
    r['maximum_coefficient_error']=verify_model(model,*arrays['train'])
    for row in observed['phase_controls']:
        subset={part:np.load(obs/f'{part}_phase_{row["seed"]}.npz') for part in ['train','check']}
        r['maximum_coefficient_error']=max(r['maximum_coefficient_error'],verify_model(row['model'],subset['train']['feature'],subset['train']['power']))
        for part in subset:verify_assessment(row['model'],subset[part]['feature'],subset[part]['power'],row[part])
    improvement=np.asarray(observed['real']['check']['relative_mse_improvement'])
    controls=np.asarray([row['check']['relative_mse_improvement'] for row in observed['phase_controls']])
    supported=(improvement>0)&np.all(improvement>controls,axis=0)
    assert supported.tolist()==observed['supported_bands']
    assert bool(model['positive'] and supported.sum()>=3)==observed['candidate_gate']
    # Audio oracle uses independent scalar PRNG, complex OSC and whole FFT convolution.
    basepath=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'
    assert sha(basepath)==rendered['parent_profile_sha256'];base=load(basepath);frames=576000;t=np.arange(frames)/48000
    modal=base['modal'];core=np.zeros((frames,2));phasors=[]
    for k,(f,amp,phase) in enumerate(zip(modal['frequencies_hz'],modal['amplitude_LR'],modal['initial_phase_LR'])):
        z=np.exp(2j*np.pi*np.remainder(t*f,1.))[:,None]*np.exp(1j*np.asarray(phase))
        core+=z.real*np.asarray(amp)
        if k in model['modal_indices']:phasors.append(z[:,0])
    z=np.asarray(phasors).T;b=np.asarray(model['coefficients'])
    modulation=sum((z[:,k].real[:,None]*b[k+1]+z[:,k].imag[:,None]*b[k+4]) for k in range(3))/b[0]
    assert np.all(1+modulation>0)
    for seed in [149921,277139,381611]:
        streams=[];count=frames+base['warmup_frames']
        for k,kernel in enumerate(base['kernels']):
            noise=normals(seed^(0x9E3779B97F4A7C15*(k+1)&((1<<64)-1)),count)
            h=np.asarray(kernel['taps']);n=next_fast_len(len(noise)+len(h)-1)
            y=np.fft.irfft(np.fft.rfft(noise,n)*np.fft.rfft(h,n),n)[base['warmup_frames']:count]*kernel['gain']
            streams.append(y[:,None]*np.array([[1.,kernel['right_over_left']]]))
        for amount in [0.,.5,1.]:
            gain=np.sqrt(1+amount*modulation);detail=np.zeros_like(core)
            for k,stream in enumerate(streams):detail+=stream*(gain[:,k-2,None] if k>=2 else 1)
            label=f'{round(amount*100):03d}_{seed}';actual=sf.read(trial/f'mix_{label}.wav',always_2d=True)[0]
            d=sf.read(trial/f'detail_{label}.wav',always_2d=True)[0]
            error=max(float(abs(actual-core-detail).max()),float(abs(d-detail).max()))
            assert error<3e-8;r['maximum_FLOAT_error']=max(error,r['maximum_FLOAT_error'])
            if amount==0:
                old=sf.read(a.workspace/f'baselines/idle_texture_v2/evidence/trial1/fine_{seed}.wav',always_2d=True)[0]
                assert np.array_equal(actual,old)
            r['renders'].append(dict(seed=seed,amount=amount,FLOAT_error=error))
        print(dict(seed=seed,audited=True),flush=True)
    invariant=a.workspace/'baselines/idle_microtexture_c_v1/inputs'
    C=load(invariant/'C_files_sha256.json');voices=load(invariant/'voice_files_sha256.json')
    assert len(C)==612 and len(voices)==67
    for name,h in {**C,**voices}.items():assert sha(repo/name)==h,name
    r.update(result='observation_parameters_and_all9_audio_verified',observation_sha256=sha(obs/'report.json'),
        input_report_sha256=sha(trial/'report.json'),train_only_parameters=True,zero_FLOAT_exact=True,
        C_H_unchanged=612,old_voices_unchanged=67,timbre_accepted=False,
        phase_observer_is_not_source_detector=True,engine_common_phase_qualification=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],maximum_FLOAT_error=r['maximum_FLOAT_error']),flush=True)
