"""Blockwise stereo band envelopes: spectra, covariance and modulation timescales."""
import numpy as np


def measure(audio, plan):
    rate, size, hop = (plan[k] for k in ('sample_rate','size','hop'))
    block = plan['block_frames']
    hz = np.fft.rfftfreq(size,1/rate)
    starts = np.arange(0,block-size+1,hop)
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    scale = np.ones(len(hz))/(size*np.sum(window*window));scale[1:-1] *= 2
    masks = np.array([(hz>=lo)&(hz<hi) for lo,hi in plan['bands']])
    design = np.column_stack((np.ones(len(starts)),np.linspace(-1,1,len(starts))))
    observations = []
    for at in range(0,len(audio)-block+1,block):
        frame = audio[at+starts[:,None]+np.arange(size)]
        z = np.fft.rfft(frame*window[None,:,None],axis=1)
        power = np.einsum('wfc,bf->wbc',abs(z)**2*scale[None,:,None],masks)
        amplitude = np.sqrt(np.maximum(power,0))
        relative = amplitude/np.maximum(amplitude.mean(axis=0),1e-20)
        flat = relative.reshape(len(starts),-1)
        motion = (flat-design@np.linalg.lstsq(design,flat,rcond=None)[0]).reshape(relative.shape)
        covariance = np.einsum('wbc,wdc->cbd',motion,motion)/len(starts)
        variance = np.mean(motion*motion,axis=0)
        cv = np.sqrt(variance)
        normalization = np.sqrt(np.maximum(np.diagonal(covariance,axis1=1,axis2=2),0))
        denominator = normalization[:,:,None]*normalization[:,None,:]
        correlation = np.divide(covariance,denominator,out=np.zeros_like(covariance),where=denominator>1e-20)
        lr = np.divide(np.mean(motion[:,:,0]*motion[:,:,1],axis=0),cv[:,0]*cv[:,1],
                       out=np.zeros(len(plan['bands'])),where=cv[:,0]*cv[:,1]>1e-20)
        autocorrelation = []
        for lag in plan['lags_frames']:
            cross = np.mean(motion[:-lag]*motion[lag:],axis=0)
            autocorrelation.append(np.divide(cross,variance,out=np.zeros_like(cross),where=variance>1e-20))
        # One-sided rectangular periodogram after the explicit linear detrend.
        # Sum over all bins equals mean squared relative envelope, by Parseval.
        spectrum = abs(np.fft.rfft(motion,axis=0))**2/len(starts)**2
        if len(starts)%2 == 0:
            spectrum[1:-1] *= 2
        else:
            spectrum[1:] *= 2
        mod_hz = np.fft.rfftfreq(len(starts),hop/rate)
        mod_power = np.array([spectrum[(mod_hz>=lo)&(mod_hz<hi)].sum(axis=0)
                              for lo,hi in plan['modulation_bands_hz']])
        mask = (mod_hz>=.5)&(mod_hz<=25)
        peak_hz = mod_hz[mask][np.argmax(spectrum[mask],axis=0)]
        observations.append(dict(power=power,envelope=motion,cv=cv,covariance=covariance,
            correlation=correlation,lr_correlation=lr,autocorrelation=np.array(autocorrelation),
            modulation_power=mod_power,modulation_peak_hz=peak_hz,
            parseval_error=np.max(abs(spectrum.sum(axis=0)-variance))))
    if not observations:
        raise ValueError('Need at least one complete source block')
    return {k:np.array([r[k] for r in observations]) for k in observations[0]} | dict(
        window_starts=starts,modulation_hz=mod_hz,frequency_hz=hz)


def summarize(data):
    off = ~np.eye(data['covariance'].shape[-1],dtype=bool)
    covariance = data['covariance'].mean(axis=0)
    modulation = data['modulation_power'].mean(axis=0)
    return dict(blocks=len(data['cv']),windows_per_block=len(data['window_starts']),
        mean_power_LR=data['power'].mean(axis=(0,1)).tolist(),
        median_cv_LR=np.median(data['cv'],axis=0).tolist(),
        covariance_LR=covariance.tolist(),
        median_abs_crossband_correlation_LR=np.median(abs(data['correlation'][:,:,off]),axis=(0,2)).tolist(),
        median_lr_envelope_correlation=np.median(data['lr_correlation'],axis=0).tolist(),
        median_autocorrelation=np.median(data['autocorrelation'],axis=0).tolist(),
        modulation_power=modulation.tolist(),
        modulation_fraction=np.divide(modulation,modulation.sum(axis=0),out=np.zeros_like(modulation),
            where=modulation.sum(axis=0)>1e-20).tolist(),
        maximum_parseval_error=float(data['parseval_error'].max()))


def scalar_power_check(audio,data,plan):
    """Direct trigonometric DFT for every bin of two bands, on selected frames."""
    size, rate = plan['size'],plan['sample_rate']
    at = np.arange(size);window = .5-.5*np.cos(2*np.pi*at/size)
    errors = []
    for frame in (0,17,51,83):
        start = data['window_starts'][frame]
        for band in (0,3,6):
            lo,hi = plan['bands'][band]
            bins = np.flatnonzero((data['frequency_hz']>=lo)&(data['frequency_hz']<hi))
            phase = 2*np.pi*bins[:,None]*at/size
            z = (np.cos(phase)-1j*np.sin(phase))@(audio[start:start+size]*window[:,None])
            actual = (abs(z)**2).sum(axis=0)*2/(size*np.sum(window*window))
            expected = data['power'][0,frame,band]
            floor = max(float(data['power'][0,frame].max())*1e-8,1e-20)
            errors.append(float(np.max(abs(actual-expected)/np.maximum(expected,floor))))
    return max(errors)


def phase_surrogate(audio, seed):
    """Offline diagnostic only; preserve the full-length stereo spectral matrix."""
    rng = np.random.default_rng(seed)
    z = np.fft.rfft(audio,axis=0)
    rotation = np.exp(2j*np.pi*rng.random(len(z)))
    rotation[0] = 1
    if len(audio)%2 == 0:
        rotation[-1] = 1
    result = np.fft.irfft(z*rotation[:,None],n=len(audio),axis=0)
    check = np.fft.rfft(result,axis=0)
    before = np.column_stack((abs(z[:,0])**2,abs(z[:,1])**2,z[:,0].conj()*z[:,1]))
    after = np.column_stack((abs(check[:,0])**2,abs(check[:,1])**2,check[:,0].conj()*check[:,1]))
    error = float(abs(after-before).max()/max(float(abs(before).max()),1e-30))
    return result,error
