"""Local diagnostics for a shared acoustic clock; never assigns physical RPM."""
import numpy as np
from phase_clock_v1.projection import carrier_rows

def diagnostics(audio,reference):
    result={}
    for order in range(1,21):
        _,values,q=carrier_rows(audio,order)
        result[str(order)]=dict(fitted=order==reference,
            coherence_LR=(abs(values.mean(axis=0))/np.maximum(np.mean(abs(values),axis=0),1e-30)).tolist(),
            supported_fraction=float(q['supported'].mean()))
    return result

def frequency(positions):
    return (positions[1:]+positions[:-1])*.5,1/(1024*np.diff(positions))

def agreement(first,second,start,stop):
    t=np.arange(start,stop,.001);ta,fa=frequency(first);tb,fb=frequency(second)
    assert t[0]>=max(ta[0],tb[0]) and t[-1]<=min(ta[-1],tb[-1])
    a=np.interp(t,ta,fa);b=np.interp(t,tb,fb);relative=abs(a-b)/(.5*(a+b))
    return dict(interval=[start,stop],absolute_hz_quantiles=np.percentile(abs(a-b),[50,95,100]).tolist(),
        relative_quantiles=np.percentile(relative,[50,95,100]).tolist(),
        passed=bool(np.percentile(relative,95)<=.05 and max(relative)<=.10),
        rule='Local independent estimates: p95<=5percent and maximum<=10percent over the same source times')
