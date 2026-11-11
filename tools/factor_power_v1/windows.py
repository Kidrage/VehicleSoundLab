"""Observe frozen log-magnitude directions under controlled window changes."""
import numpy as np
from scipy import signal


def observe(audio,model,plan,config,origin):
    size=plan['cycle_frames']*config['cycles'];support=2*plan['cycle_frames']
    centers=np.arange(support+origin,len(audio)-support+1,plan['hop'])
    starts=centers-size//2
    window=np.ones(size) if config['kind']=='rect' else .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    bins=np.arange(1,plan['harmonics']+1)*config['cycles']
    z=np.array([np.fft.rfft(audio[at:at+size]*window[:,None],axis=0)[bins]*2/window.sum() for at in starts])
    logs=np.log(np.maximum(abs(z),np.maximum(model['rms']*1e-6,1e-20)[None,:]))
    centered=(logs-logs.mean(axis=0)).reshape(len(logs),-1)
    basis=model['basis'].transpose(1,0,2).reshape(len(model['rho']),-1)
    scores=centered@basis.T/np.sum(basis*basis,axis=1)[None,:]
    factor_rows=[]
    for k in range(3):
        values=scores[:,k];variance=float(np.mean(values**2));lag_rows=[]
        for lag in plan['lags']:
            lag_rows.append(dict(lag=lag,ratio=float(values[lag:]@values[:-lag]/max(float(values[:-lag]@values[:-lag]),1e-24))))
        factor_rows.append(dict(factor=k,variance=variance,lags=lag_rows))
    # Check actual bins with a trigonometric sum on selected source windows.
    errors=[]
    for frame in sorted({0,len(starts)//2,len(starts)-1}):
        for h in (4,36,102,170):
            phase=2*np.pi*bins[h]*np.arange(size)/size
            actual=(np.cos(phase)-1j*np.sin(phase))@(audio[starts[frame]:starts[frame]+size]*window[:,None])*2/window.sum()
            floor=max(float(abs(z[frame]).max())*1e-6,1e-20)
            errors.append(float(np.max(abs(actual-z[frame,h])/np.maximum(abs(z[frame,h]),floor))))
    mean_motion=float(20/np.log(10)*np.sqrt(np.mean(centered**2)))
    return dict(config=config['name'],origin_frame=origin,frames=len(z),
        center_seconds=[float(centers[0]/48000),float(centers[-1]/48000)],
        log_motion_db=mean_motion,factors=factor_rows,direct_DFT_relative_error=max(errors)),centers,z,scores


def known(model,phase,plan):
    index=np.arange(plan['known_duration_frames']);cycles=index/1024
    def oscillator(detune=0):
        output=np.zeros((len(index),2))
        for h in range(plan['harmonics']):
            output+=model['rms'][h]*np.cos(2*np.pi*(h+1)*(1+detune)*cycles[:,None]+phase[h])
        return output
    stationary=oscillator();cases=[('known_stationary_OSC',stationary,'Fixed harmonic magnitudes/phases; no imposed AM')]
    for seed in plan['known_noise_seeds']:
        rng=np.random.default_rng(seed)
        sos=signal.butter(4,10000,fs=48000,output='sos')
        noise=signal.sosfilt(sos,rng.normal(size=(len(index)+12000,2)),axis=0)[12000:]
        # A known constant scaling, not blockwise AGC.
        noise*=np.sqrt(np.mean(stationary**2)/np.mean(noise**2))*10**(plan['known_noise_relative_rms_db']/20)
        cases.append(('known_stationary_noise_'+str(seed),stationary+noise,
            'Stationary OSC plus stationary lowpass Gaussian input; no imposed source AM'))
    cases.append(('known_fixed_detune',oscillator(plan['known_constant_detune']),
        'Fixed amplitudes with fixed0.1percent detuning; no imposed AM'))
    modulation=plan['known_AM_log_depth']*np.sin(2*np.pi*plan['known_AM_hz']*index/48000)
    am=np.cos(2*np.pi*5*cycles)[:,None]*np.exp(modulation[:,None])*np.array([[.2,.14]])
    cases.append(('known_single_carrier_AM',am,'Known1.5Hz log-amplitude modulation of harmonic5'))
    return cases
