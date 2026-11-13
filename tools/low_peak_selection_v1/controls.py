"""Known moving/missing/adjacent signals separate continuity from selection."""
import numpy as np
from .trace import window,anchor,stages


def run(plan):
    rate=48000;n=plan['analysis_frames'];hop=plan['analysis_hop'];t=np.arange(2*rate)/rate
    examples={};report={}
    stationary=.2*np.cos(2*np.pi*75.31*t+.3)+.05*np.cos(2*np.pi*191.47*t+.8)
    x=np.column_stack((stationary,.7*stationary))
    rows=[window(x[j:j+n],rate,plan) for j in range(0,len(x)-n+1,hop)]
    errors=[min(abs(f-75.31) for f in row['final_frequencies_hz']) for row in rows]
    assert max(errors)<.04
    examples['stationary']=x;report['stationary']=dict(maximum_frequency_error_hz=max(errors),all_windows_present=True)
    phase=2*np.pi*(75*t+5*t*t)
    y=.2*np.cos(phase+.4);x=np.column_stack((y,.7*y))
    rows=[window(x[j:j+n],rate,plan) for j in range(0,len(x)-n+1,hop)]
    truth=[75+10*(j+(n-1)/2)/rate for j in range(0,len(x)-n+1,hop)]
    measured=[min(row['final_frequencies_hz'],key=lambda f:abs(f-q)) for row,q in zip(rows,truth)]
    error=max(abs(f-q) for f,q in zip(measured,truth));assert error<.04,error
    center=measured[len(measured)//2]
    fraction=np.mean([anchor(row,center,3)['status']=='supported' for row in rows])
    assert fraction<plan['minimum_observed_fraction']
    examples['moving']=x;report['moving']=dict(truth_hz=truth,measured_hz=measured,
        maximum_frequency_error_hz=error,fixed_anchor_support=float(fraction),
        meaning='Known continuous chirp fails fixed-frequency inventory support; not a missing physical source')
    a=.2*np.cos(2*np.pi*76*t+.4);a[rate:]=0
    y=a+.1*np.cos(2*np.pi*84*t+.8);x=np.column_stack((y,.7*y))
    rows=[window(x[j:j+n],rate,plan) for j in range(0,len(x)-n+1,hop)]
    final=[anchor(row,76,3) for row in rows[-2:]]
    assert all(row['status']=='absent' for row in final)
    assert all(any(abs(f-84)<.04 for f in row['final_frequencies_hz']) for row in rows[-2:])
    examples['missing_with_neighbour']=x;report['missing_with_neighbour']=dict(no_substitution_in_absent_windows=True,
        meaning='Persistent adjacent84Hz does not replace missing76Hz')
    # Pure selector control: artificial power cells, not a waveform-resolution claim.
    power=np.full(n//2+1,1e-12);power[38]=1.;power[40]=.5
    rows,final=stages(power,rate,n,plan)
    selected=[row for row in rows if row['bin'] in [38,40]]
    assert len(selected)==2 and sum(row['passed']['distance'] for row in selected)==1
    report['spacing_stage']=dict(raw_peaks=len(selected),after_distance=1,artificial_spectrum_only=True)
    return report,examples
