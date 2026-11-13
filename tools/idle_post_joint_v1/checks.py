"""Nonstationary tensor oracle, followed by both families' inverse controls."""
import itertools
import numpy as np
from idle_joint_budget_v1.budget import solve,pack
from .operator import joint_operator,family_matrix,PAIRS


def fixture():
    h=np.array([[[.8,.3],[.2,-.1],[.1,.4],[.3,.2]],
                [[.4,-.1],[.5,.2],[.2,.3],[.1,-.2]],
                [[.1,.5],[.2,.1],[.7,-.2],[.3,.4]],
                [[.2,.1],[.1,.3],[.2,-.1],[.8,.2]]])
    g=np.array([[1.,.7,1.2,.8],[.9,1.3,.8,1.1],[1.2,.8,1.1,.9]])
    return h[None,...]*g[:,None,:,None]


def run(folder):
    from idle_joint_budget_v1.checks import run as stationary
    folder.mkdir();old=folder/'stationary';old.mkdir();legacy=stationary(old)
    response=fixture();operator,bound=joint_operator(response,np.zeros((4,4)))
    assert np.array_equal(bound,np.zeros_like(bound))
    # Exact marked-Gaussian frame: mean0, covarianceI, fourth even latent D=3ones.
    q=[];weights=[]
    for active in [False,True]:
        for digits in itertools.product(range(3),repeat=4):
            q.append((2*np.sqrt(3) if active else 0)*(np.asarray(digits)-1))
            weights.append((.25 if active else .75)*np.prod([2/3 if d==1 else 1/6 for d in digits]))
    q=np.asarray(q);weights=np.asarray(weights);cov=q.T@(weights[:,None]*q)
    tensor=np.empty((4,4,4,4))
    for i,j,k,l in itertools.product(range(4),repeat=4):
        tensor[i,j,k,l]=weights@(q[:,i]*q[:,j]*q[:,k]*q[:,l])-cov[i,j]*cov[k,l]-cov[i,k]*cov[j,l]-cov[i,l]*cov[j,k]
    expected=[]
    for at in range(3):
        rows=[]
        for b,c in PAIRS:
            value=0.
            for i,j,k,l in itertools.product(range(4),repeat=4):
                value+=tensor[i,j,k,l]*np.sum(response[at,b,i]*response[at,b,j]*response[at,c,k]*response[at,c,l])
            rows.append(value)
        expected.append(rows)
    prediction=family_matrix(operator,3)@np.full(10,3.)
    error=float(abs(prediction-expected).max());assert error<1e-10,error
    W=np.array([[1.,0,0,0],[.2,.9,0,0],[.1,.15,.8,0],[.05,.1,.2,.7]])
    positive=W@W.T;negative=np.eye(4);negative[0,1]=negative[1,0]=2
    controls=[]
    for family,multiplier in [('variance_factors',3),('compound_sign_groups',1)]:
        A=family_matrix(operator,multiplier).mean(axis=0)
        for name,latent in [('positive',positive),('indefinite',negative)]:
            target=A@pack(latent);solution=solve(A,target,np.ones(10),family)
            status='nonnegative_factor_CERTIFIED' if name=='positive' else 'latent_indefinite_REJECTED'
            assert solution['status']==status and abs(np.asarray(solution['latent'])-latent).max()<1e-10
            controls.append(dict(family=family,name=name,A=A.tolist(),target=target.tolist(),solution=solution))
        duplicate=np.tile(response[:,:1],(1,4,1,1));degenerate=family_matrix(joint_operator(duplicate,np.zeros((4,4)))[0],multiplier).mean(axis=0)
        solution=solve(degenerate,np.ones(10),np.ones(10),family)
        assert solution['status']=='rank_deficient_UNKNOWN'
        controls.append(dict(family=family,name='rank_deficient',A=degenerate.tolist(),target=np.ones(10).tolist(),solution=solution))
    np.savez_compressed(folder/'nonstationary_tensor.npz',response=response,operator=operator,expected=expected,q=q,weights=weights,tensor=tensor)
    return dict(legacy=legacy,nonstationary_tensor_error=error,inverse_controls=controls)
