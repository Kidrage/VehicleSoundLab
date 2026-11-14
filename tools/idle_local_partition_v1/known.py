"""Known projection/AM resolution/negative coherent-power controls before source reads."""
import numpy as np
from idle_phase_amplitude_v1.known import run as observer_controls
from .partition import partition,budget


def run():
    qualified,fixtures=observer_controls()
    frequencies=fixtures['frequencies'];amplitudes=fixtures['amplitudes']
    report=dict(observer_controls=qualified,cases=[]);arrays={}
    for label in ['constant','nonlinearFM','AM','combined']:
        audio=fixtures[label+'_audio'];z=fixtures[label+'_truth_phasors']
        out=partition(audio,frequencies,z)
        static_error=float(abs(out['static_residual']).max());dynamic_error=float(abs(out['dynamic_residual']).max())
        if label in ['constant','nonlinearFM']:
            assert static_error<1e-12 and dynamic_error<1e-12,(label,static_error,dynamic_error)
        else:assert dynamic_error<=.003 and dynamic_error<static_error,(label,static_error,dynamic_error)
        report['cases'].append(dict(label=label,static_error_FS=static_error,dynamic_error_FS=dynamic_error))
        arrays[label+'_audio']=audio;arrays[label+'_phasors']=z
        arrays[label+'_static']=out['static_main'];arrays[label+'_dynamic']=out['dynamic_main']
    t=np.arange(144000)/48000;angle=2*np.pi*t[:,None]*frequencies+np.linspace(-.9,.7,13)
    amplitude=np.tile(amplitudes,(len(t),1));amplitude[:,[1,2,4]]*=1+.2*np.cos(2*np.pi*8*t[:,None])
    x=np.sum(amplitude*np.cos(angle),axis=1);audio=np.column_stack((x,x));z=np.exp(1j*angle[:,[1,2,4]])
    out=partition(audio,frequencies,z);rms=float(np.sqrt(np.mean(out['dynamic_residual']**2)))
    assert rms>.003
    report['cases'].append(dict(label='fast8Hz_AM_unresolved_counterexample',dynamic_residual_rms=rms))
    arrays.update(fast_audio=audio,fast_phasors=z)
    neighbor=partition(fixtures['neighbor_audio'],frequencies,fixtures['neighbor_phasors'])
    neighbor_rms=float(np.sqrt(np.mean(neighbor['dynamic_residual']**2)))
    assert neighbor_rms>.003
    report['cases'].append(dict(label='unmodeled8Hz_neighbor_counterexample',dynamic_residual_rms=neighbor_rms))
    arrays.update(neighbor_audio=fixtures['neighbor_audio'],neighbor_phasors=fixtures['neighbor_phasors'])
    # A coherent anti-phase residual makes total-minus-main negative despite positive residual power.
    n=100800;t=np.arange(n)/48000;main=np.column_stack([.08*np.cos(2*np.pi*187.3*t)]*2)
    residual=-.5*main;audio=main+residual;result=budget(audio,main,residual,frequencies)
    negative=float((result['total']-result['main']).min());assert negative<0
    assert result['residual'].sum()>0 and result['cross'].sum()<0
    report['cases'].append(dict(label='coherent_negative_debt_counterexample',minimum_total_minus_main=negative,
        residual_power=float(result['residual'].sum()),signed_cross=float(result['cross'].sum()),
        budget_identity_error=result['identity_error']))
    arrays.update(negative_audio=audio,negative_main=main,negative_residual=residual,frequencies=frequencies)
    return report,arrays
