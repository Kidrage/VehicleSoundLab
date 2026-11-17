"""Bounded offline band-gain calibration of the existing finite event kernel."""
from copy import deepcopy
import numpy as np
from scipy import optimize,signal
from .model import synth,validate
from .measure import spectrum


def calibrate(profile,observation,duration):
    # Frequencies, phases, filters and envelopes stay fixed. Only <=8 group
    # gains are fitted. Cross terms include the shared procedural-noise seed.
    bands=observation['bands'];groups=[];waves=[]
    for k,band in enumerate(bands):
        low,high=band['hz']
        members=[i for i,m in enumerate(profile['modes']) if low<=m['hz']<high]
        for kind,indices in [('modes',members),('bands',[k])]:
            if not indices or not any(profile[kind][i]['amplitude']>0 for i in indices):continue
            component=deepcopy(profile)
            for category in ('modes','bands'):
                for i,row in enumerate(component[category]):
                    if category!=kind or i not in indices:row['amplitude']=0.
            wave=synth(component,seconds=duration)
            if np.mean(wave*wave)<=1e-30:continue
            groups.append((kind,indices));waves.append(wave)
    target_total=observation['scoped_excess_mean_square']
    target=np.array([b['excess_power'] for b in bands],dtype=float)
    target*=target_total/max(float(target.sum()),1e-30)
    if not waves or target_total<=0:
        return validate(profile),dict(scope_band_fit_qualified=False,reason='No positive scoped fit target or basis')
    waves=np.column_stack(waves);count=waves.shape[1]
    gram=np.zeros((len(bands),count,count))
    for i in range(count):
        for j in range(i,count):
            frequency,cross=signal.csd(waves[:,i],waves[:,j],48000,nperseg=min(2048,len(waves)),detrend=False)
            df=frequency[1]-frequency[0]
            for k,b in enumerate(bands):
                selected=(frequency>=b['hz'][0])&(frequency<b['hz'][1])
                gram[k,i,j]=gram[k,j,i]=float(cross[selected].real.sum()*df)
    # Small-band floors avoid dividing by zero; every selected band still has
    # an explicit residual. Nothing outside the declared scope is fitted.
    scale=np.maximum(target,target_total*1e-6)
    diagonal=np.diagonal(gram,axis1=1,axis2=2)
    powers,_=optimize.nnls(diagonal/scale[:,None],target/scale,maxiter=200)
    initial=np.clip(np.sqrt(powers),1e-6,63.)
    def residual(gain):
        power=np.einsum('i,bij,j->b',gain,gram,gain)
        return (power-target)/scale
    result=optimize.least_squares(residual,initial,bounds=(0,64),max_nfev=160,
        ftol=1e-10,xtol=1e-10,gtol=1e-10)
    fitted=deepcopy(profile)
    for gain,(kind,indices) in zip(result.x,groups):
        for i in indices:fitted[kind][i]['amplitude']*=float(gain)
    level=max([1.]+[m['amplitude']/4 for m in fitted['modes']]+[b['amplitude']/8 for b in fitted['bands']])
    amplitude_fits=level<=8
    fitted['level']=min(8.,level)
    for category in ('modes','bands'):
        for row in fitted[category]:row['amplitude']/=level
    validate(fitted)
    actual=synth(fitted,seconds=duration);frequency,psd=spectrum(actual[:,None]);df=frequency[1]-frequency[0]
    rows=[]
    for k,b in enumerate(bands):
        power=float(psd[(frequency>=b['hz'][0])&(frequency<b['hz'][1])].sum()*df)
        # Near-zero targets have an absolute ceiling rather than an arbitrary dB ratio.
        significant=target[k]>=target_total*1e-6
        error_db=float(10*np.log10(max(power,1e-30)/max(target[k],1e-30)))
        passed=abs(error_db)<=3 if significant else power<=target_total*2e-6
        rows.append(dict(hz=b['hz'],target_power=float(target[k]),generated_power=power,
            error_db=error_db,significant_target=bool(significant),passed=bool(passed)))
    return fitted,dict(scope_band_fit_qualified=bool(amplitude_fits and all(r['passed'] for r in rows)),
        scope_band_fit=rows,component_groups=len(groups),optimizer_evaluations=result.nfev,
        optimizer_terminated=bool(result.success),amplitude_contract_fits=amplitude_fits,
        calibration='Nonnegative gains on fixed modal groups and existing SOS bands; exact finite-waveform Welch cross-power matrix; <=8 gains, max160 optimizer evaluations. No new runtime DSP.',
        seed=27431,level_fit_target_excess_power=target_total,
        scope_band_fit_limits='Each significant declared band must be within ±3 dB. This seed-specific band balance is not transient/physical-source/timbre acceptance.')
