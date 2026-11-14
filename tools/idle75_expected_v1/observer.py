"""Sparse gain lift and exact centering of expected finite-window moments."""
import numpy as np
from scipy import sparse
from idle75_clock_v1.row import weights
from idle75_expected_v1.kernel import gain_covariance

LAGS=[0,2,5,10]


def compile(h,constant,reference,grid_rate):
    # Grid indices -1..ceil(3*rate)+1, four local cubic support points.
    count=3*grid_rate+3;times=(np.arange(count)-1)/grid_rate
    starts=np.arange(12000,122401,960);rows=[];columns=[];values=[]
    for row,first in enumerate(starts):
        q=np.arange(first,first+9600)/48000*grid_rate;k=np.floor(q).astype(int);w,_=weights(q-k)
        # q floor uses support -1/0/1/2; times index has an extra -1 origin.
        for i in range(4):
            cols=k+i
            summed=np.bincount(cols,weights=(h[row]/reference).real*w[:,i],minlength=count)
            active=np.flatnonzero(summed);rows.extend([row]*len(active));columns.extend(active.tolist());values.extend(summed[active].tolist())
    B=sparse.csr_matrix((values,(rows,columns)),shape=(116,count))
    assert abs(np.asarray(B.sum(axis=1)).ravel()-np.sum((h/reference).real,axis=1)).max()<1e-12
    return dict(operator=B,constant=(constant/reference).real,times=times,grid_rate=grid_rate)


def centered(value):
    return value-value.mean(axis=0)[None,:]-value.mean(axis=1)[:,None]+value.mean()


def moments(compilation,covariance,derivatives,mean,mean_derivative):
    B=compilation['operator'];K=np.asarray((B@covariance)@B.T);K=centered(K)
    row_sum=np.asarray(B.sum(axis=1)).ravel();mu=compilation['constant']+mean*row_sum;mu-=mu.mean()
    all_values=[];jac=[]
    derivative_matrices=[centered(np.asarray((B@d)@B.T)) for d in derivatives]
    dm=mean_derivative*row_sum;dm-=dm.mean()
    for lag in LAGS:
        count=len(mu)-lag
        meanpart=float(mu[:count]@mu[lag:]/count)
        all_values.append(float(np.diag(K,k=lag).mean()+meanpart))
        grad=[float(np.diag(d,k=lag).mean()) for d in derivative_matrices]
        grad[1]+=float((dm[:count]@mu[lag:]+mu[:count]@dm[lag:])/count)
        jac.append(grad)
    return np.array(all_values),np.array(jac),K


class Expected:
    def __init__(self,model,compilations):
        self.model=model;self.compilations=compilations;self.last_parameters=None;self.last_value=None;self.calls=0

    def __call__(self,parameters):
        p=np.asarray(parameters)
        if self.last_parameters is not None and np.array_equal(p,self.last_parameters):return self.last_value
        C,dc,ds,mean,dmean=gain_covariance(self.model,self.compilations[0]['times'],p)
        values=[];jac=[];minimum=[]
        for compilation in self.compilations:
            value,derivative,K=moments(compilation,C,[dc,ds],mean,dmean)
            values.append(value);jac.append(derivative);minimum.append(float(np.linalg.eigvalsh(K).min()))
        self.calls+=1;self.last_parameters=p.copy()
        self.last_value=(np.mean(values,axis=0),np.mean(jac,axis=0),min(minimum))
        return self.last_value
