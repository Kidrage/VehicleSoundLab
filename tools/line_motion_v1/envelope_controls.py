"""Fixed known affine-AM fixtures plus an explicitly mismatched sinusoidal-AM case."""
import numpy as np
from .peaks import native_peaks
from .local_chirps import fit_channel as constant_fit,evaluate as constant_wave
from .local_envelopes import fit_channel,evaluate,local_envelopes
from .peak_controls import peak_controls


def fixtures(rate=48000):
    t=np.arange(rate)/rate-.5
    f=np.array([75.2,112.8,188.,82.3,37.6,45.1]);q=np.array([.3,.4,.6,-.2,.1,-.1])
    a=np.array([.5,.4,.3,.18,.14,.17]);phase=np.array([.2,.5,.8,.1,.4,.7])
    specs=[('six_constant',np.arange(6),np.zeros(6),False),
        ('six_affine',np.arange(6),np.array([.8,-.6,.4,-.8,.6,-.4]),False),
        ('single_affine',np.array([0]),np.array([.8]),False),
        ('neighbor_pair_affine',np.array([0,3]),np.array([.8,-.6]),False),
        ('six_sinusoidal_out_of_model',np.arange(6),np.zeros(6),True)]
    for name,index,s,outside in specs:
        freq=f[index].copy();chirp=q[index].copy();amp=a[index];p=phase[index]
        if name=='single_affine':freq[:]=75.19;chirp[:]=0
        envelope=1+t[:,None]*s
        if outside:envelope=1+.4*np.cos(2*np.pi*3*t[:,None]+p)
        x=(amp*envelope*np.cos(2*np.pi*(t[:,None]*freq+.5*t[:,None]**2*chirp)+p)).sum(axis=1)
        # Labels delimit original observation cells; all fitted frequencies come from their native peaks.
        labels=[75,113,188,82,38] if len(index)==6 else ([75] if len(index)==1 else [75,82])
        observed=native_peaks(np.column_stack((x,x)),rate,labels)
        selected=observed['selected_native_bin_Hz'][:,0].tolist()
        assert all(b>=0 for b in selected)
        if len(index)==6:
            extra=[p['native_bin_Hz'] for p in observed['candidates'][4][0] if p['native_bin_Hz']!=selected[4]]
            if outside and len(extra)!=1:
                yield dict(id=name,out_of_model=True,inventory_unresolved=True,
                    selected_bins_Hz=selected,additional_low_candidates_Hz=extra,
                    reason='Sinusoidal AM produces multiple low-region native peaks; do not force a six-component assignment')
                continue
            assert len(extra)==1,'Fixed six-tone fixture must have exactly two low-region observed peaks'
            selected+=extra
        bins=np.array(selected,dtype=float)
        yield dict(id=name,audio=x,nominal=bins,true_frequency=freq,true_chirp=chirp,true_slope=s,
            out_of_model=outside,original_observation_labels=labels)


def controls(rate=48000):
    prior=peak_controls(observer=local_envelopes);t=np.arange(rate)/rate-.5;rows=[]
    for fixture in fixtures(rate):
        if fixture.get('inventory_unresolved'):
            rows.append(dict(**fixture,gate_applied=False,passed=None,fit_attempted=False));continue
        x=fixture['audio'];bins=fixture['nominal'];m=len(bins)
        p0,c0=constant_fit(x,rate,bins);p1,c1=fit_channel(x,rate,bins)
        # Truth is used only after observed initialization and both actual solves.
        matched=np.array([np.argmin(abs(fixture['true_frequency']-b)) for b in bins])
        assert len(set(matched))==len(matched)
        expected=fixture['true_frequency'][matched];q=fixture['true_chirp'][matched];s=fixture['true_slope'][matched]
        old_error=float(abs(bins+p0[:m]-expected).max());new_error=float(abs(bins+p1[:m]-expected).max())
        old_q=float(abs(p0[m:2*m]-q).max());new_q=float(abs(p1[m:2*m]-q).max())
        relative=float(np.linalg.norm(evaluate(p1,bins,t)[0]-x)/np.linalg.norm(x))
        slope=float(abs(p1[4*m:5*m]-s).max())
        threshold=.001 if m==1 else .01
        passed=c1['success'] and not any(c1['at_bound']) and not any(c1['slope_at_bound']) and new_error<=threshold and slope<=.001 and relative<=1e-6
        rows.append(dict(id=fixture['id'],out_of_model=fixture['out_of_model'],gate_applied=not fixture['out_of_model'],
            passed=bool(passed) if not fixture['out_of_model'] else None,nominal_Hz=bins.tolist(),
            constant= dict(fit=c0,max_frequency_error_Hz=old_error,max_chirp_error_Hz_per_s=old_q,
                waveform_relative_error=float(np.linalg.norm(constant_wave(p0,bins,t)[0]-x)/np.linalg.norm(x))),
            affine=dict(fit=c1,max_frequency_error_Hz=new_error,max_chirp_error_Hz_per_s=new_q,
                max_slope_error_per_s=slope,waveform_relative_error=relative)))
    return dict(passed=prior['passed'] and all(r['passed'] for r in rows if r['gate_applied']),prior_controls=prior,cases=rows,
        truth_used_for_assessment_only=True,scope='Positive first-order local envelope qualification, not general AM or engine phase recovery')
