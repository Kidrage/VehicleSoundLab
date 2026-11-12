"""Validated periodic power shape, with no recorded trajectory or event pulse."""
import numpy as np

def samples(beta,frames,start=0,cycle=1024):
    phase=2*np.pi*(np.arange(start,start+frames)%cycle)/cycle
    order=np.arange(1,len(beta)//2+1)
    power=1+np.column_stack((np.cos(phase[:,None]*order),np.sin(phase[:,None]*order)))@np.asarray(beta)
    if np.min(power)<.05:raise ValueError('Periodic power shape loses positive margin')
    return np.sqrt(power)

def from_diagnostic(report,bands):
    source=next(v for v in report['observations'] if v['name']=='A_normalized_reference')
    result=[]
    for low,high in bands:
        parent=next(v for v in source['bands'] if v['band_hz'][0]<=low and v['band_hz'][1]>=high)
        beta=np.zeros(16)
        if parent['periodic_envelope_gate_passed']:
            beta=np.mean([r['coefficients'] for r in parent['periodic_envelope']],axis=0)
        wave=samples(beta,1024)
        assert abs(np.mean(wave*wave)-1)<1e-12
        result.append(dict(coefficients=beta.tolist(),parent_band_hz=parent['band_hz'],
                           enabled=bool(parent['periodic_envelope_gate_passed']),
                           minimum_power=float(min(wave*wave)),maximum_power=float(max(wave*wave))))
    return result
