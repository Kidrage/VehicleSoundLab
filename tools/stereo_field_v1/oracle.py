"""Independent scalar matrix sums, plus common-gain and channel-swap invariants."""
import math
import numpy as np
from .model import packed,fit,losses


def check(data,plan):
    maximum=0;checks=0
    for low,high in plan['bands']:
        mask=(data['hz']>=low)&(data['hz']<high);value=packed(data,mask)
        training=list(range(max(1,len(value)//2)));test=list(range(max(1,len(value)//2),len(value)))
        count=min(4,value.shape[1]);prior=1
        predicted,cells=fit(value,training,count,prior)
        # Scalar moments start at raw powers, not packed()/fit() intermediates.
        bins=np.flatnonzero(mask);normal=[sum(float(data['left'][b,k]+data['right'][b,k]) for k in bins) for b in training]
        sums=[0.,0.,0.,0.]
        for at,b in enumerate(training):
            for k in bins:
                c=data['cross'][b,k]
                for j,x in enumerate((data['left'][b,k],data['right'][b,k],c.real,c.imag)):sums[j]+=float(x)/normal[at]
        total=sums[0]+sums[1];parent=[x/total for x in sums]
        for cell in cells:
            part=[0.,0.,0.,0.]
            for at,b in enumerate(training):
                for k in bins[cell['bins']]:
                    c=data['cross'][b,k]
                    for j,x in enumerate((data['left'][b,k],data['right'][b,k],c.real,c.imag)):part[j]+=float(x)/normal[at]
            pseudo=prior*total/count;denominator=part[0]+part[1]+pseudo
            expected=np.array([(part[j]+pseudo*parent[j])/denominator for j in range(4)])
            maximum=max(maximum,float(np.max(abs(expected-np.array(cell['matrix'])))));checks+=4
        for b,actual in zip(test,losses(value,test,predicted)):
            energy=sum(float(data['left'][b,k]+data['right'][b,k]) for k in bins);answer=0
            for j,k in enumerate(bins):
                left=float(data['left'][b,k]);right=float(data['right'][b,k]);cross=complex(data['cross'][b,k]);trace=left+right
                q=(left/trace,right/trace,cross.real/trace,cross.imag/trace)
                answer+=(trace/energy)*sum(w*(predicted[j,c]-q[c])**2 for c,w in enumerate((1,1,2,2)))
            maximum=max(maximum,abs(answer-float(actual)));checks+=1
        factors=np.geomspace(.02,5,len(value))[:,None]
        scaled={**data,'left':data['left']*factors,'right':data['right']*factors,'cross':data['cross']*factors}
        swapped={**data,'left':data['right'],'right':data['left'],'cross':data['cross'].conj()}
        gained,_=fit(packed(scaled,mask),training,count,prior)
        exchanged,_=fit(packed(swapped,mask),training,count,prior)
        expected=predicted[:,[1,0,2,3]].copy();expected[:,3]*=-1
        maximum=max(maximum,float(abs(gained-predicted).max()),float(abs(exchanged-expected).max()));checks+=2*predicted.size
    assert math.isfinite(maximum) and maximum<plan['tolerances']['invariance_absolute'],maximum
    return dict(scalar_values_and_invariants=checks,maximum_absolute_error=maximum)
