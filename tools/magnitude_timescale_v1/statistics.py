"""Inspect the frozen factor model without refitting its spatial directions."""
import numpy as np


def magnitudes(audio,harmonics=300):
    starts=np.arange(0,len(audio)-1024+1,256)
    z=np.array([np.fft.rfft(audio[at:at+1024],axis=0)[1:harmonics+1]*2/1024 for at in starts])
    return starts,z


def lag_ratio(values):
    return np.sum(values[1:]*values[:-1],axis=0)/np.maximum(np.sum(values[:-1]**2,axis=0),1e-30)


def inspect(audio,model,cap):
    starts,z=magnitudes(audio)
    logs=np.log(np.maximum(abs(z),np.maximum(model['rms']*1e-6,1e-20)[None,:]))
    centered=(logs-logs.mean(axis=0)).reshape(len(starts),-1)
    basis=model['basis'].transpose(1,0,2).reshape(len(model['rho']),-1)
    energies=np.sum(basis*basis,axis=1)
    scores=centered@basis.T/energies[None,:]
    raw=lag_ratio(scores)
    residual=(centered-scores@basis).reshape(len(starts),-1,2)
    rr=np.sum(residual[1:]*residual[:-1],axis=(0,2))/np.maximum(np.sum(residual[:-1]**2,axis=(0,2)),1e-30)
    residual_variance=np.sum(model['root']**2,axis=(1,2))
    changed=dict(model,rho=np.clip(raw,-cap,cap),residual_rho=np.clip(rr,-cap,cap))
    return changed,dict(
        raw_factor_rho=raw.tolist(),existing_factor_rho=model['rho'].tolist(),
        proposed_factor_rho=changed['rho'].tolist(),
        factor_variance=energies.tolist(),raw_residual_rho=rr.tolist(),
        factor_variance_fraction_above_old_cap=float(energies[raw>.95].sum()/energies.sum()),
        residual_variance_fraction_above_old_cap=float(residual_variance[rr>.95].sum()/residual_variance.sum()),
        old_rho_recovery_max_error=float(max(abs(np.clip(raw,-.95,.95)-model['rho']).max(),
            abs(np.clip(rr,-.95,.95)-model['residual_rho']).max())),
        observation_frames=len(starts),trajectory_stored=False)


def describe(audio,orders):
    starts,z=magnitudes(audio,180)
    db=20/np.log(10)*np.log(np.maximum(abs(z),1e-20))
    t=np.linspace(-1,1,len(starts));design=np.column_stack((np.ones(len(t)),t))
    motion=(db.reshape(len(t),-1)-design@np.linalg.lstsq(design,db.reshape(len(t),-1),rcond=None)[0]).reshape(db.shape)
    rows=[]
    for order in orders:
        relative=z[:,order-1]*np.exp(-2j*np.pi*order*starts/1024)[:,None]
        angles=np.unwrap(np.angle(relative),axis=0)
        fractional=np.diff(angles,axis=0)/(2*np.pi*order*(256/48000)*46.875)
        rows.append(dict(order=order,relative_frequency_quantile_LR=np.quantile(fractional,[.05,.5,.95],axis=0).tolist(),
            maximum_phase_step_radians_LR=np.max(abs(np.diff(angles,axis=0)),axis=0).tolist(),
            minimum_power_relative_to_loudest_window_LR=(abs(relative).min(axis=0)/abs(relative).max(axis=0)).tolist(),
            meaning='Short-window phase slope mixes clock, source and interference; not measured true engine frequency'))
    return dict(harmonic_log_motion_rms_db_LR=np.sqrt(np.mean(motion**2,axis=(0,1))).tolist(),
        high_harmonic_log_motion_rms_db_LR=np.sqrt(np.mean(motion[:,102:171]**2,axis=(0,1))).tolist(),
        phase_observations=rows)


def known_ar(plan):
    rng=np.random.default_rng(plan['known_AR_seed']);rows=[]
    for rho in plan['known_AR_rhos']:
        values=np.empty(plan['known_AR_observations']);values[0]=rng.normal()
        innovations=rng.normal(size=len(values)-1)
        for i in range(1,len(values)):values[i]=rho*values[i-1]+np.sqrt(1-rho*rho)*innovations[i-1]
        observed=float(lag_ratio(values[:,None])[0])
        assert abs(observed-rho)<plan['tolerances']['known_AR_rho_absolute'],(rho,observed)
        rows.append(dict(true_rho=rho,observed_rho=observed,old_clipped_rho=float(np.clip(observed,-.95,.95))))
    return rows
