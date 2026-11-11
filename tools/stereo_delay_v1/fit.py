"""Compare scalar complex coherence with one bounded phase slope per band."""
import numpy as np


def coherence(data,blocks,mask):
    left = data['left'][blocks][:,mask].mean(axis=0)
    right = data['right'][blocks][:,mask].mean(axis=0)
    cross = data['cross'][blocks][:,mask].mean(axis=0)
    weight = np.sqrt(left*right)
    value = cross/np.maximum(weight,1e-30)
    return value,weight


def fit(data,bands,plan):
    count = len(data['left']);split = count//2
    train,test = np.arange(split),np.arange(split,count)
    delays = np.linspace(-plan['delay_bound_seconds'],plan['delay_bound_seconds'],plan['delay_grid_points'])
    records = []
    for band,(lo,hi) in enumerate(bands):
        mask = (data['hz']>=lo)&(data['hz']<hi)
        frequencies = data['hz'][mask]-(lo+hi)/2
        observed,weight = coherence(data,train,mask)
        weight = weight/max(float(weight.sum()),1e-30)
        rotations = np.exp(2j*np.pi*delays[:,None]*frequencies[None,:])
        candidates = rotations@(weight*observed)
        chosen = int(np.argmax(abs(candidates)))
        delay = float(delays[chosen]);a = candidates[chosen]
        scalar = np.sum(weight*observed)
        predicted = a*np.exp(-2j*np.pi*frequencies*delay)
        scalar_errors,delay_errors = [],[]
        for block in test:
            actual,w = coherence(data,[block],mask)
            w = w/max(float(w.sum()),1e-30)
            scalar_errors.append(float(np.sum(w*abs(actual-scalar)**2)))
            delay_errors.append(float(np.sum(w*abs(actual-predicted)**2)))
        old,new = float(np.sqrt(np.mean(scalar_errors))),float(np.sqrt(np.mean(delay_errors)))
        reduction = (old-new)/old if old>1e-8 else 0
        at_boundary = chosen in (0,len(delays)-1)
        phase_qualified = abs(a)>=plan['minimum_fitted_coherence'] and not at_boundary
        records.append(dict(hz=[lo,hi],frequency_bins=int(mask.sum()),train_blocks=train.tolist(),test_blocks=test.tolist(),
            scalar=[float(scalar.real),float(scalar.imag)],delay_seconds=delay,
            delayed_coefficient=[float(a.real),float(a.imag)],fitted_coherence=float(abs(a)),
            delay_at_bound=at_boundary,train_phase_qualified=bool(phase_qualified),
            scalar_test_rmse=old,delay_test_rmse=new,test_rmse_reduction_fraction=reduction,
            predictive_gate_passed=bool(phase_qualified and reduction>=plan['minimum_test_rmse_reduction_fraction']),
            median_detrended_envelope_cv_LR=np.median(data['detrended_envelope_cv'][:,band],axis=0).tolist()))
    return records
