"""Fixed observation controls and explicit nonidentifiable adjacent-tone example."""
import numpy as np
from .controls import controls
from .peaks import native_peaks


def peak_controls(rate=48000,observer=native_peaks):
    prior=controls(observer=observer)
    time=np.arange(6*rate)/rate
    # Analytic continuous chirp. No frequency truth is passed to the observer.
    phase=37.35*time+.5*.12*time*time
    source=sum(a*np.cos(2*np.pi*n*phase+p) for n,a,p in [(1,.15,.2),(2,.5,.6),(3,.4,.9),(5,.3,1.2)])
    source+=.18*np.cos(2*np.pi*82*time+.7)
    nominal=[[75,112,187,82,37],[75,112,188,82,37],[76,113,189,81,38]]
    rows=[]
    for block in range(3):
        for shift in (0,rate//2,rate):
            start=block*2*rate+shift
            x=source[start:start+rate]
            value=observer(np.column_stack((x,.9*x)),rate,nominal[block])
            middle=(start+rate/2)/rate
            truth=(37.35+.12*middle)*np.array([2,3,5,0,1]);truth[3]=82
            error=float(abs(value['frequency_Hz']-truth[:,None]).max())
            rows.append(dict(start_seconds=start/rate,max_frequency_error_Hz=error,
                all_roots_resolved=bool(value['root_resolved'].all()),
                nearest_bins_exact=bool(np.array_equal(value['selected_native_bin_Hz'],np.repeat(np.round(truth).astype(int)[:,None],2,axis=1))),
                passed=error<=.01 and bool(value['root_resolved'].all())))
    t=time[:rate]
    equal=np.cos(2*np.pi*75.1*t+.4)+np.cos(2*np.pi*75.3*t+.4)
    mixed=observer(np.column_stack((equal,equal)),rate,[75.])
    noise=np.random.default_rng(731091).normal(0,.1,(rate,2))
    random=observer(noise,rate,nominal[0])
    return dict(passed=prior['passed'] and all(r['passed'] for r in rows),original_controls=prior,
        extended_chirp_rows=rows,
        unresolved_source_counterexample=dict(actual_tones_Hz=[75.1,75.3],
            returned_center_Hz=mixed['frequency_Hz'].tolist(),root_resolved=mixed['root_resolved'].tolist(),
            interpretation='Two tones inside one Hann main lobe can return one resolved center; not single-source identification'),
        noise_counterexample=dict(selected_bins_Hz=random['selected_native_bin_Hz'].tolist(),
            returned_Hz=random['frequency_Hz'].tolist(),root_resolved=random['root_resolved'].tolist()),
        scope='Local peak/frequency observation qualification only; not waveform clock or physical-period detector')
