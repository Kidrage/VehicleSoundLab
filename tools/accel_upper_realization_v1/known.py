"""Direct finite observation and filter-history controls before any frozen source input is read."""
import numpy as np
from scipy import signal
from .observe import observe_block


def known():
    rng=np.random.default_rng(916231);tile=np.repeat([0,1,2],[7,13,19]);size=480;time=np.arange(len(tile)*size)/48000
    amplitude=.6+.2*np.sin(2*np.pi*5*time);other=1.6-amplitude
    x=np.column_stack([amplitude*np.sin(2*np.pi*6000*time),other*np.sin(2*np.pi*6000*time),.2*rng.standard_normal(len(time)),.1*rng.standard_normal(len(time))])
    P=np.array([.3,.6,.04,.01]);actual=observe_block(x,tile,P);power=np.array([[sum(x[w*size:(w+1)*size,i]**2)/size for i in range(4)] for w in range(len(tile))])
    residual=power.copy()
    for tag in np.unique(tile):
        kk=np.flatnonzero(tile==tag);local=np.array([sum(power[kk,i])/len(kk) for i in range(4)]);residual[kk]-=local
    expected=[]
    for lag in range(-5,6):
        pairs=[(u,u+lag) for u in range(len(tile)) if 0<=u+lag<len(tile) and tile[u]==tile[u+lag]]
        expected.append(np.array([[sum(residual[u,i]*residual[v,j] for u,v in pairs)/len(pairs) for j in range(4)] for i in range(4)]))
    expected=np.array(expected);error=float(abs(actual['signed_lagged']-expected).max());assert error<1e-12 and expected[5,0,1]<0
    assert abs(actual['theoretical_normalized']-expected/np.outer(P,P)).max()<1e-12
    mean=power.mean(axis=0);assert abs(actual['measured_normalized']-expected/np.outer(mean,mean)).max()<1e-12
    normalization_difference=float(abs(actual['theoretical_normalized']-actual['measured_normalized']).max());assert normalization_difference>1e-3
    scaled=observe_block(x*3,tile,P*9);permutation=[2,0,3,1];swapped=observe_block(x[:,permutation],tile,P[permutation])
    for key in ['theoretical_normalized','measured_normalized']:
        assert abs(scaled[key]-actual[key]).max()<1e-12
        assert abs(swapped[key]-actual[key][:,permutation][:,:,permutation]).max()<1e-12
    rejected=False
    try:observe_block(x[:-1],tile,P)
    except ValueError:rejected=True
    assert rejected
    history=rng.standard_normal((127,4));q=np.array([[.7,-.5,.3,1.],[.2,.1,-.2,.3],[-.1,.2,.4,-.2]])
    full=np.column_stack([signal.oaconvolve(history[:,i],q[:,i])[:len(history)] for i in range(4)])[2:]
    explicit=np.array([[sum(q[k,i]*history[n-k,i] for k in range(3)) for i in range(4)] for n in range(2,len(history))])
    filter_error=float(abs(full-explicit).max());assert filter_error<1e-12
    zero_start=np.column_stack([signal.lfilter(q[:,i],[1.],history[2:,i]) for i in range(4)])
    missing_history_error=float(abs(full-zero_start).max());assert missing_history_error>.01
    return dict(explicit_signed_energy_error=error,negative_cross_preserved=True,scaling_and_permutation=True,
        power_denominator_difference=normalization_difference,partial_window_rejected=True,
        full_history_convolution_error=filter_error,zero_start_counterexample_error=missing_history_error),dict(audio=x,tile=tile,
        theoretical_power=P,power=power,signed_lagged=expected,history=history,filter=q,filtered=full,explicit_filtered=explicit,**{k:actual[k] for k in ['theoretical_normalized','measured_normalized','spectrum','starts']})
