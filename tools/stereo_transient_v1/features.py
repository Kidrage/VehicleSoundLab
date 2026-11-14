"""Native stereo STFT powers and broad-dip evidence; no pitch or physical-state inference."""
import numpy as np


def observe(audio,start,plan):
    rate=plan['sample_rate'];size=plan['window_frames'];hop=plan['hop_frames']
    starts=np.arange(0,len(audio)-size+1,hop)
    window=.5-.5*np.cos(2*np.pi*np.arange(size)/size)
    hz=np.fft.rfftfreq(size,1/rate)
    scale=np.full(len(hz),1/(size*np.sum(window**2)));scale[1:-1]*=2
    masks=np.array([(hz>=lo)&(hz<hi) for lo,hi in plan['bands_hz']])
    powers=[];crosses=[]
    for at in range(0,len(starts),64):
        frames=audio[starts[at:at+64,None]+np.arange(size)[None,:]]
        z=np.fft.rfft(frames*window[None,:,None],axis=1)
        powers.append(np.einsum('wfc,bf->wbc',abs(z)**2*scale[None,:,None],masks))
        cross=z[:,:,0].conj()*z[:,:,1]*scale[None,:]
        crosses.append(cross@masks.T)
    power=np.concatenate(powers);cross=np.concatenate(crosses)
    correlation=cross/np.sqrt(np.maximum(power[:,:,0]*power[:,:,1],plan['minimum_power_FS2']**2))
    return dict(seconds=start+(starts+size/2)/rate,starts=starts,power=power,cross=cross,
        correlation=correlation,RL_dB=10*np.log10(np.maximum(power[:,:,1],plan['minimum_power_FS2'])/
            np.maximum(power[:,:,0],plan['minimum_power_FS2'])),frequency_hz=hz)


def analyze(data,plan):
    time=data['seconds'];power=data['power'].mean(axis=2)
    lo,hi=plan['baseline_seconds'];before=(time>=lo)&(time<hi)
    baseline=np.median(power[before],axis=0)
    relative=10*np.log10(np.maximum(power,plan['minimum_power_FS2'])/np.maximum(baseline,plan['minimum_power_FS2']))
    curve=np.median(relative[:,plan['primary_bands']],axis=1)
    lo,hi=plan['search_seconds'];candidates=np.flatnonzero((time>=lo)&(time<hi))
    if not len(candidates) or sum(before)<3:raise ValueError('Declared measurement regions unavailable')
    dip=int(candidates[np.argmin(curve[candidates])]);center=float(time[dip])
    lo,hi=plan['recovery_delay_seconds'];after=np.flatnonzero((time>=center+lo)&(time<=center+hi))
    if not len(after):raise ValueError('Declared recovery support unavailable')
    peak=int(after[np.argmax(curve[after])]);level=float(curve[dip]);recovery=float(curve[peak])
    qualified=(level<=-plan['dip_drop_db'] and recovery-level>=plan['recovery_rise_db'] and
        recovery>=-plan['recovery_within_baseline_db'])
    regions={}
    for name,(lo,hi) in dict(baseline=plan['baseline_seconds'],dip=[center-.02,center+.02],post=plan['post_region_seconds']).items():
        keep=(time>=lo)&(time<hi)
        p=data['power'][keep].mean(axis=0);c=data['cross'][keep].mean(axis=0)
        rho=c/np.sqrt(np.maximum(p[:,0]*p[:,1],plan['minimum_power_FS2']**2))
        regions[name]=dict(seconds=[float(lo),float(hi)],frames=int(sum(keep)),power_LR=p.tolist(),
            RL_dB=(10*np.log10(np.maximum(p[:,1],plan['minimum_power_FS2'])/np.maximum(p[:,0],plan['minimum_power_FS2']))).tolist(),
            cross_re_im=np.column_stack([c.real,c.imag]).tolist(),
            correlation_re_im=np.column_stack([rho.real,rho.imag]).tolist())
    result=dict(dip_center_seconds=center,dip_relative_db=level,recovery_center_seconds=float(time[peak]),
        recovery_relative_db=recovery,recovery_rise_db=recovery-level,
        descriptive_broad_dip_recovery=bool(qualified),regions=regions,
        waveform_or_clock_resampled=False,physical_shift_identified=False)
    return result,dict(relative_band_dB=relative,primary_curve_dB=curve,baseline_power=baseline)
