"""Known mixtures assess observations; truth never initializes the estimator."""
import numpy as np
from .fit import fit
from .link import link


def wave(frequencies,rates,amplitudes,phases,time):
    angle=2*np.pi*(time[:,None]*np.asarray(frequencies)+.5*time[:,None]**2*np.asarray(rates))+phases
    return np.column_stack((np.cos(angle)@amplitudes,.67*np.cos(angle+np.arange(len(frequencies))*.13)@amplitudes))


def match_truth(result,frequencies,rates,plan):
    assert result['success'],result
    rows=result['lines'];assert len(rows)==len(frequencies),(len(rows),frequencies,result)
    ferror=max(abs(row['frequency_hz']-f) for row,f in zip(rows,frequencies))
    qerror=max(abs(row['chirp_hz_per_second']-q) for row,q in zip(rows,rates))
    assert all(row['eligible'] for row in rows),result
    assert ferror<=plan['known_frequency_error_hz'],(ferror,result)
    assert qerror<=plan['known_chirp_error_hz_per_second'],(qerror,result)
    assert max(result['weighted_relative_residual_LR'])<=plan['known_waveform_relative_error'],result
    return dict(frequency_error_hz=float(ferror),chirp_error_hz_per_second=float(qerror))


def run(plan,progress=lambda value:None):
    rate=plan['sample_rate'];n=plan['frames'];t=np.arange(n)/rate-.25
    fixtures={};rows=[]
    cases=[('stationary',[75.31],[0],[.2],[.31]),
        ('moving',[85.31],[20],[.2],[.31]),
        ('neighbor',[75.31,84.23],[4,0],[.18,.13],[.31,-.7]),
        ('missing_low',[84.23],[0],[.13],[-.7])]
    for name,f,q,amp,phase in cases:
        x=wave(f,q,np.asarray(amp),np.asarray(phase),t);observed,state=fit(x,rate,plan)
        row=dict(id=name,**match_truth(observed,f,q,plan),observation=observed)
        if name=='missing_low':assert all(abs(r['frequency_hz']-75.31)>1 for r in observed['lines'])
        fixtures[name+'_audio']=x;fixtures[name+'_reconstructed']=state['reconstructed']
        rows.append(row);progress(dict(control=name,status='passed'))
    # Moving and fixed low-frequency structures coexist in the SAME recording.
    f=np.array([61.37,94.71,127.13,175.89,224.47,285.13]);q=np.array([6,0,12,0,18,0])
    amp=np.array([.17,.13,.14,.09,.11,.07]);phase=np.array([.2,-.5,.8,.4,-.7,1.1])
    tt=np.arange(96000)/rate-1;mixture=wave(f,q,amp,phase,tt);observations=[];errors=[]
    for start in range(0,len(mixture)-n+1,plan['hop']):
        observed,state=fit(mixture[start:start+n],rate,plan)
        center=(start+n/2)/rate-1
        errors.append(match_truth(observed,f+q*center,q,plan));observations.append(observed)
        progress(dict(control='moving_plus_fixed',window=len(observations),status='passed'))
    correspondence=link(observations,plan)
    qualified=[r for r in correspondence['tracks'] if len(r['windows'])==7]
    assert len(qualified)==6,correspondence
    assert sum(r['classification']=='locally_stationary' for r in qualified)==3
    assert sum(r['classification']=='locally_moving' for r in qualified)==3
    fixtures['mixed_audio']=mixture
    rows.append(dict(id='moving_plus_fixed',errors=errors,observations=observations,correspondence=correspondence))
    scaled,scaled_state=fit(.21*mixture[36000:60000],rate,plan)
    original=observations[3]
    gain_f=max(abs(a['frequency_hz']-b['frequency_hz']) for a,b in zip(scaled['lines'],original['lines']))
    gain_q=max(abs(a['chirp_hz_per_second']-b['chirp_hz_per_second']) for a,b in zip(scaled['lines'],original['lines']))
    assert len(scaled['lines'])==6 and gain_f<=.001 and gain_q<=.001,(gain_f,gain_q,scaled)
    rows.append(dict(id='gain',frequency_error_hz=float(gain_f),chirp_error_hz_per_second=float(gain_q),observation=scaled))
    fixtures['gain_audio']=.21*mixture[36000:60000]
    # Link-only counterexample: disappearance is not a licence to change identity.
    first=[dict(frequency_hz=75.,chirp_hz_per_second=0.,eligible=True),dict(frequency_hz=84.,chirp_hz_per_second=0.,eligible=True)]
    second=[dict(frequency_hz=84.,chirp_hz_per_second=0.,eligible=True)]
    missing=link([dict(lines=first),dict(lines=second)],plan)
    assert missing['frames'][1][0]['track_id']==missing['frames'][0][1]['track_id']
    assert missing['frames'][1][0]['track_id']!=missing['frames'][0][0]['track_id']
    # Any two possible predecessors terminate identity, even if one is stronger.
    ambiguous=link([dict(lines=[dict(frequency_hz=80.,chirp_hz_per_second=0.,eligible=True),
        dict(frequency_hz=80.4,chirp_hz_per_second=0.,eligible=True)]),
        dict(lines=[dict(frequency_hz=80.2,chirp_hz_per_second=0.,eligible=True)])],plan)
    assert ambiguous['frames'][1][0]['predecessor']=='ambiguous'
    rows.append(dict(id='missing_and_ambiguous_correspondence',missing=missing,ambiguous=ambiguous))
    silence,state=fit(np.zeros((n,2)),rate,plan);assert not silence['lines'] and silence['reason']=='no_candidates'
    fixtures['silence_audio']=np.zeros((n,2));rows.append(dict(id='silence',observation=silence))
    rng=np.random.Generator(np.random.PCG64(572091));noise=rng.normal(0,.12,(n,2))
    observed,state=fit(noise,rate,plan)
    assert not any(row['eligible'] for row in observed['lines']),observed
    fixtures['noise_audio']=noise;rows.append(dict(id='noise',observation=observed))
    progress(dict(control='noise',status='passed'))
    crossing=wave([80.,80.],[60.,-60.],np.array([.15,.15]),np.array([.2,.2]),t)
    observed,state=fit(crossing,rate,plan)
    assert not any(row['eligible'] for row in observed['lines']),observed
    fixtures['crossing_audio']=crossing;rows.append(dict(id='crossing',observation=observed))
    progress(dict(control='crossing',status='passed'))
    return dict(passed=True,cases=rows,truth_used_for_initialization=False,
        scope='Finite known controls qualify only this local observation and correspondence contract'),fixtures
