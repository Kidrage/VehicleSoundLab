"""Full signed error powers with all cross terms and independent LR axes."""
import numpy as np


def analyze(raw, fir, phase, fitted_grid, continuous, *, rate=48000):
    values = [np.asarray(x) for x in (raw,fir,phase,fitted_grid,continuous)]
    if (rate!=48000 or values[0].ndim!=2 or values[0].shape[1]!=2 or len(values[0])<4096
            or any(v.shape!=values[0].shape or np.iscomplexobj(v) or not np.isfinite(v).all() for v in values)):
        raise ValueError('Aligned complete finite48k stereo signals required')
    raw,fir,phase,fitted_grid,continuous = values
    components = np.stack((fir-raw,phase-fir,fitted_grid-phase,continuous-fitted_grid),axis=1)
    total = continuous-raw
    closure = total-components.sum(axis=1)
    columns = components.reshape(len(raw),8)
    starts = np.arange(0,len(raw)-4096+1,256)
    indices = starts[:,None]+np.arange(4096)[None]
    window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    transformed = np.fft.rfft(columns[indices]*window[None,:,None],axis=1)
    reference = np.fft.rfft(raw[indices]*window[None,:,None],axis=1)
    delta = np.fft.rfft(total[indices]*window[None,:,None],axis=1)
    endpoint = np.r_[1.,np.full(2047,2.),1.]
    groups = np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*rate/4096,side='right')
    grams, reference_power, error_power = [],[],[]
    for band in range(6):
        selected = groups==band
        X = transformed[:,selected]
        w = endpoint[selected]
        grams.append(np.einsum('wki,wkj,k->ij',X,X.conj(),w,optimize=True))
        reference_power.append(np.einsum('wkc,wkc,k->c',reference[:,selected],reference[:,selected].conj(),w,optimize=True).real)
        error_power.append(np.einsum('wkc,wkc,k->c',delta[:,selected],delta[:,selected].conj(),w,optimize=True).real)
    grams,reference_power,error_power = map(np.asarray,(grams,reference_power,error_power))
    autos = np.stack([grams[:,2*j:2*j+2,2*j:2*j+2].diagonal(axis1=1,axis2=2).real for j in range(4)],axis=1)
    cross = np.zeros((6,4,4,2))
    for i in range(4):
        for j in range(i+1,4):
            cross[:,i,j] = 2*np.stack([grams[:,2*i+c,2*j+c].real for c in range(2)],axis=1)
    recovered = autos.sum(axis=1)+cross.sum(axis=(1,2))
    relative = [[float(np.sqrt(e/r)) if r>0 else (0. if e==0 else None)
                 for e,r in zip(ep,rp)] for ep,rp in zip(error_power,reference_power)]
    return dict(components=components,total_error=total,closure=closure,
        band_joint_Gram=grams,band_component_auto_power=autos,band_component_signed_cross_power=cross,
        band_reference_power=reference_power,band_error_power=error_power,band_recovered_error_power=recovered,
        time_joint_Gram=columns.T@columns,starts=starts),dict(
        component_names=['source_FIR','declared_grid_reconstruction','grid_fit_residual','continuous_OSC_minus_grid_reconstruction'],
        channel_order=['FIR_L','FIR_R','grid_L','grid_R','fit_L','fit_R','continuity_L','continuity_R'],
        frames=len(raw),windows=len(starts),rate=rate,
        band_error_NRMSE_LR=relative,
        closure_max_FS=float(np.max(abs(closure))),
        signed_power_closure_max_reference_relative=float(np.max(abs(recovered-error_power)/np.maximum(reference_power,1e-300))),
        native_reconstruction_is_diagnostic_not_physical_inverse=True,
        error_component_powers_are_not_additive_percentages=True)
