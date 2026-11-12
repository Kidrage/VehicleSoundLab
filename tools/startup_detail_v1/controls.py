"""Known covariance and direct-DFT checks, independent of the fitted recording."""
import numpy as np
from scipy import signal
from .budget import additive
from residual_osc_v1.spectrum import matrices
from stereo_field_v1.budget import matrix, scalar_minimum


def checks():
    records=[]
    examples=[('independent',np.eye(2),np.diag([.2,.3]),True),
        ('complex',np.array([[2,-.4j],[.4j,1]]),np.eye(2)*.2,True),
        ('cross_excess',np.eye(2),np.array([[.8,.4],[.4,.8]]),False),
        ('diagonal_excess',np.eye(2),np.diag([2.,.1]),False),
        ('no_debt',np.eye(2),np.eye(2),True),
        ('rank_one',np.ones((2,2)),np.eye(2)*.2,False)]
    for name,t,b,ok in examples:
        row=additive(t,b);assert row['accepted']==ok
        assert abs(scalar_minimum(t-b)-np.linalg.eigvalsh(t-b)[0])<1e-12
        if ok:assert row['reconstruction_error_relative']<1e-12
        else:assert row['power']==[0,0] and row['coherence']==[0,0]
        u=np.diag([1,np.exp(.73j)])
        rotated=additive(u@t@u.conj().T,u@b@u.conj().T)
        assert rotated['accepted']==ok
        assert abs(rotated['minimum_eigenvalue_relative']-row['minimum_eigenvalue_relative'])<1e-12
        records.append(dict(name=name,passed=True,**row))
    # Independent scalar periodogram energy and conjugation convention.
    n=8192;t=np.arange(n)/48000
    x=np.column_stack([.2*np.cos(2*np.pi*703.125*t),.3*np.cos(2*np.pi*703.125*t+.6)])
    actual=matrices(x,[(500,900)])[0];truth=np.array([.02,.045])
    assert np.max(abs(np.asarray(actual['power'])-truth))<1e-12
    assert abs(complex(*actual['cross'])-.03*np.exp(.6j))<1e-12
    w=signal.windows.hann(2048,sym=False);accum=np.zeros((2,2),complex)
    for at in range(0,n-2048+1,512):
        # DFT rows below are formed explicitly, independent of Welch/csd.
        k=np.arange(22,39);kernel=np.exp(-2j*np.pi*k[:,None]*np.arange(2048)[None,:]/2048)
        z=kernel@(x[at:at+2048]*w[:,None])
        accum+=np.array([[np.sum(abs(z[:,0])**2),np.sum(z[:,0]*z[:,1].conj())],
                         [np.sum(z[:,0].conj()*z[:,1]),np.sum(abs(z[:,1])**2)]])*2/(w@w)/2048
    accum/=len(range(0,n-2048+1,512))
    error=float(np.max(abs(accum-matrix(actual))));assert error<1e-12
    records.append(dict(name='known stereo tone and direct DFT',passed=True,max_matrix_error=error))
    return records
