"""Finite known AM/FM and generic generator checks, before real source access."""
import numpy as np
from .analysis import observe,compile_statistics
from .envelope import states,gains
from .voice import render
from idle_modal_v1.modal import render as old_render


def run(plan):
    rate=plan['sample_rate'];time=np.arange(3*rate)/rate;fixtures={};rows=[]
    for name,f,a,p in [('offgrid_three',[75.31,150.71,262.17],[.2,.08,.035],[.2,-.7,.4]),
        ('offgrid_two',[83.17,193.41],[.17,.05],[-.4,.7])]:
        modal=dict(frequencies_hz=f,amplitude_LR=[[v,.7*v] for v in a],initial_phase_LR=[[v,v+.13] for v in p])
        x=old_render(modal,len(time),rate);observation=observe(x,f,plan)
        error=float(abs(abs(observation['coefficients'])/np.asarray(a)-1).max())
        assert error<=plan['known_static_relative_error'],(name,error)
        stats,evidence,_=compile_statistics(observation,plan)
        assert max(evidence['raw_log_std'])<=1e-10
        actual,state,normal=render(modal,stats,12347,rate,149921,0,1.1)
        assert np.array_equal(actual,old_render(modal,12347,rate,1.1))
        other,_,_=render(modal,stats,12347,rate,277139,1,1.1)
        assert abs(other-actual).max()<=1e-10
        rows.append(dict(id=name,magnitude_relative_error=error,max_log_std=max(evidence['raw_log_std']),zero_exact=True))
        fixtures[name+'_audio']=x
    # Bin-centred design has mutually orthogonal Hann-weighted columns.
    f=np.array([75.,190.]);a=np.array([.18,.07]);phase=np.array([.31,-.7]);depth=np.array([.2,.1])
    slow=1+np.sin(2*np.pi*.8*time[:,None]+np.array([0.,.4]))*depth
    left=np.sum(slow*a*np.cos(2*np.pi*time[:,None]*f+phase),axis=1)
    x=np.column_stack((left,.67*left));observation=observe(x,f,plan)
    n=plan['observation_frames'];w=np.sin(np.pi*np.arange(n)/n)**2
    local=(np.arange(n)-n/2)/rate;dtft=[];averaged=[]
    for start in observation['starts']:
        tile=x[start:start+n,0]
        dtft.append([2*np.sum(w*tile*np.exp(-2j*np.pi*ff*local))/w.sum() for ff in f])
        averaged.append(np.sum(w[:,None]*slow[start:start+n],axis=0)/w.sum()*a)
    dtft_error=float(abs(observation['coefficients']-dtft).max())
    amplitude_error=float(abs(abs(observation['coefficients'])-averaged).max())
    assert dtft_error<=1e-11 and amplitude_error<=plan['known_AM_weighted_amplitude_error'],(dtft_error,amplitude_error)
    rows.append(dict(id='known_AM',finite_DTFT_error=dtft_error,weighted_amplitude_error=amplitude_error))
    fixtures['AM_audio']=x;fixtures['AM_coefficients']=observation['coefficients']
    # A fixed-amplitude nonlinear FM can bias windowed magnitudes; preserve the measurement.
    left=.2*np.cos(2*np.pi*75.31*time-(1.2/1.6)*np.cos(2*np.pi*1.6*time)+.4)
    x=np.column_stack((left,.67*left));observation=observe(x,[75.31],plan)
    stats,evidence,_=compile_statistics(observation,plan)
    spurious=float(evidence['raw_log_std'][0]);assert spurious<=plan['known_FM_log_std_limit'],spurious
    rows.append(dict(id='known_FM',spurious_log_std=spurious,
        note='Not zero: this proxy is not a physical AM detector or a universal FM error bound.'))
    fixtures['FM_audio']=x;fixtures['FM_coefficients']=observation['coefficients']
    # Independent analytic covariance and marginal lognormal power identities.
    covariance=np.array([[.04,.01],[.01,.09]]);alpha=.7;u=.31
    blend=np.array([1-u,u]);variance=float(blend@np.array([[1,alpha],[alpha,1]])@blend)
    normalized=blend/np.sqrt(variance)
    error=abs(float(normalized@np.array([[1,alpha],[alpha,1]])@normalized)-1)
    assert error<1e-14
    model=dict(covariance=covariance.tolist(),factor=np.linalg.cholesky(covariance).tolist(),alpha=alpha,hop_frames=9600)
    state,normal=states(model,12347,149921);gain=gains(model,state,12347,.5)
    expected=np.empty_like(state);L=np.linalg.cholesky(covariance);expected[0]=L@normal[0]
    for i in range(1,len(state)):expected[i]=alpha*expected[i-1]+np.sqrt(1-alpha*alpha)*L@normal[i]
    assert abs(state-expected).max()<1e-14
    assert np.array_equal(gains(model,state,12347,0),np.ones_like(gain))
    # Fully singular covariance is supported, with exact unity and no invented variation.
    zero=dict(covariance=np.zeros((2,2)).tolist(),factor=np.zeros((2,2)).tolist(),alpha=0.,hop_frames=9600)
    z,_=states(zero,12347,149921);assert np.array_equal(gains(zero,z,12347,1),np.ones((12347,2)))
    modal=dict(frequencies_hz=[83.17,193.41],amplitude_LR=[[.2,.1],[.03,.04]],initial_phase_LR=[[.1,.3],[.2,-.1]])
    actual,state,normal=render(modal,model,12347,rate,149921,.5,1.1)
    gain=gains(model,state,12347,.5);oracle=np.zeros_like(actual);t=np.arange(len(actual))/rate
    for k,(ff,amp,phi) in enumerate(zip(modal['frequencies_hz'],modal['amplitude_LR'],modal['initial_phase_LR'])):
        oracle+=gain[:,k,None]*np.asarray(amp)*np.cos(2*np.pi*ff*1.1*t[:,None]+phi)
    oscillator_error=float(abs(actual-oracle).max());assert oscillator_error<=2e-12
    rows.append(dict(id='generator',normalized_interpolation_variance_error=error,oscillator_error=oscillator_error,
        semidefinite_zero_exact=True,power_identity='E exp(2sZ-2s^2V)=1 for zero-mean Gaussian Z with varianceV',duration_independent_of_pitch=True))
    return dict(passed=True,checks=rows,physical_AM_identified=False),fixtures
