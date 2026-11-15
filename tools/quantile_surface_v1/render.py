"""New conditional phase law on the ORIGINAL saved amplitudes/common/U."""
import numpy as np
from .surface import evaluate
from conditional_phase_time_v1.observer import power_statistics
from carrier_transfer_v1.groups import indices


def generate(bundle,amplitude,common,uniform,root,edges,bands,name):
    frames,h,_=amplitude.shape;n=np.arange(frames);orders=np.arange(1,h+1)
    tags=indices(h,root,edges);x=np.clip((orders*root-19200)/2400,0,1);taper=1-3*x*x+2*x*x*x
    group=np.zeros((frames,len(edges)-1,2));power=np.zeros((frames,2*len(bands)));cross=np.zeros((frames,len(bands)),complex)
    maximum=np.empty(h);rms=np.empty(h)
    for j in range(h):
        product=amplitude[:,j,0]*amplitude[:,j,1]/bundle['mean_product'][j]
        delta=evaluate(product,uniform[:,j],bundle['knots'][j],bundle[name][j],bundle['low'][j],bundle['high'][j])
        change=np.diff(delta);maximum[j]=abs(change).max();rms[j]=np.sqrt(np.mean(change*change))
        amp=amplitude[:,j]*taper[j];carrier=2*np.pi*(n%1024)/1024*(j+1)
        for c,sign in ((0,1),(1,-1)):group[:,tags[j],c]+=amp[:,c]*np.cos(carrier+common[:,j]+sign*delta/2)
        for b,(lo,hi) in enumerate(bands):
            if lo<=orders[j]*root<hi:
                power[:,2*b:2*b+2]+=amp*amp/2
                cross[:,b]+=amp[:,0]*amp[:,1]*np.exp(1j*delta)/2
    return group,dict(maximum_phase_step=maximum,RMS_phase_step=rms,
                      **{'instant_'+k:v for k,v in power_statistics(power,cross).items()})
