"""Known ensembles and inverse failures before any real recording is inspected."""
import itertools,math
import numpy as np
from idle_joint_cumulant_v1.moments import joint
from .budget import operator,pack,solve


def run(folder):
    h=np.array([[[.8,.3],[.2,-.1],[.1,.4],[.3,.2]],
                [[.4,-.1],[.5,.2],[.2,.3],[.1,-.2]],
                [[.1,.5],[.2,.1],[.7,-.2],[.3,.4]],
                [[.2,.1],[.1,.3],[.2,-.1],[.8,.2]]])
    q,weight=[],[]
    for mark in [0,1]:
        for digits in itertools.product(range(3),repeat=4):
            q.append(mark*2*np.sqrt(3.)*(np.array(digits)-1))
            weight.append((.25 if mark else .75)*math.prod(2/3 if d==1 else 1/6 for d in digits))
    q,w=np.array(q),np.array(weight)
    first=q@h[:,:,0].T
    second=q@h[:,:,1].T
    audio=(first[:,None,:]+second[None,:,:]).reshape(-1,4)
    weights=(w[:,None]*w[None,:]).ravel()
    observed=joint(audio,weights)
    expected=operator(h,3)@pack(np.full((4,4),3.))
    error=float(abs(pack(np.array(observed['cumulant']))-expected).max())
    assert error<1e-10,error
    np.savez_compressed(folder/'Gaussian_FIR.npz',h=h,q=q,q_weights=w,audio=audio,weights=weights)
    out=dict(Gaussian_FIR=dict(error=error,observation=observed,expected=expected.tolist()))
    # Conditional on Poisson count, each band's signed sum is an independent binomial sum.
    amplitude=np.array([.7,1.,1.2,.9]);rate=.125
    samples=[];weights=[];counts=[]
    for count in range(13):
        probability=math.exp(-rate)*rate**count/math.factorial(count)
        for negatives in itertools.product(range(count+1),repeat=4):
            samples.append(amplitude*(count-2*np.array(negatives)))
            weights.append(probability*math.prod(math.comb(count,k)/2**count for k in negatives))
            counts.append(count)
    samples,weights=np.array(samples),np.array(weights)
    measured=joint(samples,weights)
    C=rate*np.outer(amplitude**2,amplitude**2)
    error=float(abs(np.array(measured['cumulant'])-C).max())
    assert error<1e-11,error
    np.savez_compressed(folder/'Poisson_binomial.npz',audio=samples,weights=weights,counts=counts,amplitude=amplitude,rate=rate)
    out['Poisson_binomial']=dict(error=error,observation=measured,expected=C.tolist(),
        total_probability=float(weights.sum()),samples=len(samples))
    W=np.array([[1.,0,0,0],[.2,.9,0,0],[.1,.15,.8,0],[.05,.1,.2,.7]])
    positive=W@W.T
    indefinite=np.eye(4)
    indefinite[0,1]=indefinite[1,0]=2.
    out['inverse_controls']=[]
    for family,multiplier in [('variance_factors',3),('compound_sign_groups',1)]:
        A=operator(h,multiplier)
        for name,C in [('positive',positive),('indefinite',indefinite)]:
            target=A@pack(C)
            solved=solve(A,target,np.ones(10),family)
            assert np.allclose(solved['latent'],C,atol=1e-10)
            expected='nonnegative_factor_CERTIFIED' if name=='positive' else 'latent_indefinite_REJECTED'
            assert solved['status']==expected,(family,name,solved)
            out['inverse_controls'].append(dict(family=family,name=name,A=A.tolist(),target=target.tolist(),solution=solved))
        degenerate=operator(np.tile(h[:1],(4,1,1)),multiplier)
        solved=solve(degenerate,np.ones(10),np.ones(10),family)
        assert solved['status']=='rank_deficient_UNKNOWN'
        out['inverse_controls'].append(dict(family=family,name='rank_deficient',A=degenerate.tolist(),target=np.ones(10).tolist(),solution=solved))
    return out
