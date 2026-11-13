"""Known correspondence cases and six-component omitted-line control."""
import numpy as np
from .correspondence import correspond
from .local_chirps import fit_channel,evaluate,local_chirps
from .peak_controls import peak_controls


def graph_controls():
    def nodes(*pairs):return [dict(frequency_Hz=f,power=p) for f,p in pairs]
    swap=[nodes((37,4),(45,1)),nodes((37,1),(45,4))]
    matched=correspond(swap)
    rows=[dict(id='rank_swap',passed=[x['track_id'] for x in matched['frames'][0]]==[x['track_id'] for x in matched['frames'][1]])]
    merged=correspond([nodes((37,2),(40,1)),nodes((38,3))])
    rows.append(dict(id='merge',passed=merged['frames'][1][0]['predecessor']=='ambiguous'))
    split=correspond([nodes((38,3)),nodes((37,2),(40,1))])
    rows.append(dict(id='split',passed=all(n['predecessor']=='ambiguous' for n in split['frames'][1])))
    missing=correspond([nodes((37,4),(45,1)),nodes((45,4))])
    rows.append(dict(id='missing',passed=len(missing['frames'][1])==1 and missing['frames'][1][0]['track_id']==1))
    tied=correspond([nodes((37,1),(41,1)),nodes((39,1))])
    rows.append(dict(id='tie',passed=tied['frames'][1][0]['predecessor']=='ambiguous'))
    permuted=correspond([list(reversed(x)) for x in swap])
    rows.append(dict(id='permutation',passed=permuted==matched))
    scaled=correspond([[dict(n,power=n['power']*7) for n in frame] for frame in swap])
    rows.append(dict(id='gain_invariant',passed=[[n['track_id'] for n in f] for f in scaled['frames']]==[
        [n['track_id'] for n in f] for f in matched['frames']]))
    return dict(passed=all(r['passed'] for r in rows),cases=rows,
        scope='Discrete graph rules only; noise or merged acoustic components may still supply native peaks')


def controls():
    graph=graph_controls();prior=peak_controls(observer=local_chirps)
    rate=48000;t=np.arange(rate)/rate-.5
    frequencies=np.array([75.2,112.8,188.,82.3,37.6,45.1])
    rates=np.array([.3,.4,.6,-.2,.1,-.1])
    amplitude=np.array([.5,.4,.3,.18,.14,.17])
    phase=np.array([.2,.5,.8,.1,.4,.7])
    x=(amplitude*np.cos(2*np.pi*(t[:,None]*frequencies+.5*t[:,None]**2*rates)+phase)).sum(axis=1)
    # Native FFT choices from fixed observation cells, adding the independently present37Hz peak.
    observed=local_chirps(np.column_stack((x,.9*x)),rate,[75,113,188,82,38])
    selected=observed['selected_native_bin_Hz'][:,0].tolist()
    # A literal data-native peak near37/38 must be observed, not inserted as a truth frequency.
    candidates=observed['candidates'][4][0]
    extra=[p['native_bin_Hz'] for p in candidates if p['native_bin_Hz']!=selected[4]]
    assert len(extra)==1,'Known fixture must expose two resolved low-region peaks without a search'
    bins=np.array(selected+extra,dtype=float)
    parameters,fit=fit_channel(x,rate,bins)
    reconstructed=evaluate(parameters,bins,t)[0]
    expected=np.array([frequencies[np.argmin(abs(frequencies-bin))] for bin in bins])
    error=float(abs(bins+parameters[:len(bins)]-expected).max())
    relative=float(np.linalg.norm(reconstructed-x)/np.linalg.norm(x))
    # Fixed zero-bandwidth omission diagnostic; no waveform truth initializes either fit.
    winner=observed['local_chirp_fit'][0]
    original=evaluate(np.array(winner['fitted_parameters']),np.array(winner['nominal_Hz']),t)[0]
    kernel=np.exp(-2j*np.pi*37.6*t)*np.sin(np.pi*np.arange(rate)/rate)**2
    omitted=float(abs(np.sum((x-original)*kernel))/np.sum(abs(kernel)))
    return dict(passed=graph['passed'] and prior['passed'] and fit['success'] and error<=.01 and relative<=1e-6,
        graph=graph,prior_local_controls=prior,six_tone_control=dict(selected_bins_Hz=bins.tolist(),
            max_frequency_error_Hz=error,waveform_relative_error=relative,fit=fit,
            omitted_component_projection=omitted,truth_used_for_assessment_only=True))
