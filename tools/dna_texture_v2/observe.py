"""Period-neighbourhood repeat and held-out periodic-envelope diagnostics."""
import numpy as np
from scipy import signal

def analytic_band(x,band,plan):
    taps=signal.firwin(plan['filter_taps'],band,pass_zero=False,fs=plan['sample_rate'])
    y=signal.fftconvolve(x,taps[:,None],mode='same',axes=0)
    # Hilbert is applied before discarding support, not separately to each half.
    z=signal.hilbert(y,axis=0)
    margin=plan['edge_discard_frames']
    return z[margin:-margin]

def repeat(z,plan):
    rows=[];errors=[]
    for channel in range(2):
        v=z[:,channel];corr=signal.correlate(v,v,mode='full',method='fft')[len(v)-1:]
        energy=np.r_[0,np.cumsum(abs(v)**2)]
        for cycles in plan['cycle_lags']:
            center=cycles*plan['acoustic_cycle_frames'];width=round(center*plan['lag_relative_search'])
            lags=np.arange(center-width,center+width+1)
            denom=np.sqrt((energy[-1]-energy[lags])*energy[len(v)-lags])
            values=abs(corr[lags])/np.maximum(denom,1e-30)
            idx=int(np.argmax(values))
            direct=np.vdot(v[:-center],v[center:])
            errors.append(abs(direct-corr[center])/max(abs(direct),energy[-1]*1e-12))
            rows.append(dict(channel=channel,cycles=cycles,maximum_repeat=float(values[idx]),
                             best_lag_frames=int(lags[idx]),nominal_repeat=float(values[width])))
    return rows,float(max(errors))

def envelope(z,plan):
    size=plan['envelope_smoothing_frames'];count=len(z)-size+1
    power=signal.fftconvolve(abs(z)**2,np.ones((size,1))/size,mode='valid',axes=0)
    at=np.arange(count)+plan['edge_discard_frames']+(size-1)/2
    # Eight Fourier orders, fixed before data. Test both half directions;
    # absolute source phase is common. No fitted lag/RPM/search or copied trace.
    phase=2*np.pi*at/plan['acoustic_cycle_frames']
    orders=np.arange(1,plan['envelope_fourier_orders']+1)
    X=np.column_stack((np.cos(phase[:,None]*orders),np.sin(phase[:,None]*orders)))
    split=count//2;rows=[]
    for channel in range(2):
        values=power[:,channel]
        for reverse in (False,True):
            train=slice(split,None) if reverse else slice(None,split)
            test=slice(None,split) if reverse else slice(split,None)
            train_y=values[train]/values[train].mean()-1
            test_y=values[test]/values[test].mean()-1
            beta=np.linalg.lstsq(X[train],train_y,rcond=None)[0]
            prediction=X[test]@beta
            mse=float(np.mean((test_y-prediction)**2));flat=float(np.mean(test_y**2))
            gain=1-mse/flat if flat>1e-20 else None
            rows.append(dict(channel=channel,reverse=reverse,flat_MSE=flat,periodic_MSE=mse,
                             heldout_improvement=gain,coefficients=beta.tolist()))
    return rows

def observe(x,plan):
    rows=[]
    for band in plan['bands_hz']:
        z=analytic_band(x,band,plan)
        correlation,error=repeat(z,plan);env=envelope(z,plan)
        valid=all(v['heldout_improvement'] is not None and v['heldout_improvement']>=.10 for v in env)
        rows.append(dict(band_hz=band,repeat=correlation,direct_correlation_relative_error=error,
                         periodic_envelope=env,periodic_envelope_gate_passed=valid))
    return rows
