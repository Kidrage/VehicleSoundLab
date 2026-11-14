"""Optional within-band shape on the same original oscillator/resonator engine."""
import numpy as np
from scipy import signal
from idle_phase_difference_v1.features import matrix
from idle_positive_power_v1.model import predict
from idle_phase_recipe_v1.phase import spline,phasors
from idle_phase_recipe_v1.render2 import phase_audio,noise
from .split import split,shape


def render(profile,phase_model,values,law,probability,shape_model,seed,seconds):
    frames=seconds*48000;warm=profile['warmup_frames'];count=frames+warm
    motion=spline(phase_model,values)
    _,main=phase_audio(profile,phase_model,motion,frames,48000)
    beta=np.asarray(shape_model['coefficients']);q=np.empty((frames,4));delta=np.empty_like(q)
    for start in range(0,frames,24000):
        t=np.arange(start,min(frames,start+24000))/48000
        feature=matrix(phasors(phase_model,motion,t),hop=1,trim=0)
        q[start:start+len(t)]=predict(law,feature)
        delta[start:start+len(t)]=beta[0]+feature@beta[1:]
    details={str(amount):np.zeros_like(main) for amount in [0.,.5,1.]}
    traces=[]
    for index,kernel in enumerate(profile['kernels']):
        if index<2:
            excitation=noise(seed,index,count,'gaussian')
        else:
            p=probability[index-2];u=noise(seed,index,count,'uniform');n=noise(seed,index,count,'normal')
            excitation=np.where(u<p,n/np.sqrt(p),0.)
        original=signal.oaconvolve(excitation,kernel['taps'])[:count]*kernel['gain']
        ratio=np.array([1.,kernel['right_over_left']])
        if index<2:
            for detail in details.values():detail+=original[warm:,None]*ratio
            continue
        model=shape_model['branches'][index-2];lo,hi=split(original,model['crossover_hz'])
        root=np.sqrt(q[:,index-2]);d=delta[:,index-2]
        for amount in [0.,.5,1.]:
            y=shape(original[warm:],lo[warm:],hi[warm:],d,amount,model)
            details[str(amount)]+=y[:,None]*root[:,None]*ratio
        traces.append(np.column_stack((original[warm:],lo[warm:],hi[warm:])))
    result={'main':main}
    for amount,detail in details.items():
        result['detail_'+amount]=detail;result['mix_'+amount]=main+detail
    return result,dict(q=q,delta=delta,branches=np.array(traces))
