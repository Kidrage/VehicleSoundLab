"""White-input matrix traces and exact finite Gaussian quadrature before source models."""
import numpy as np
from numpy.polynomial.hermite import hermgauss
from .model import conditional_mean


def covariance(h):
    n=len(h);return np.array([[sum(np.dot(h[k,i],h[k+t,i]) for k in range(n-t)) for i in range(4)] for t in range(n)])


def white_trace(h,g,tile,size):
    frames=len(g);n=len(h);inputs=h.shape[2];power=np.sum(h*h,axis=(0,2));means=[]
    for i in range(4):
        T=np.zeros((frames,(frames+n-1)*inputs))
        for a in range(frames):
            for k in range(n):T[a,(a+n-1-k)*inputs:(a+n-k)*inputs]=g[a,i]*h[k,i]
        B=[]
        for w in range(len(tile)):
            rows=T[w*size:(w+1)*size];B.append(rows.T@rows/(size*power[i]))
        m=np.array([np.trace(b) for b in B]);C=np.array([[2*np.sum(b*c.T) for c in B] for b in B]);A=np.eye(len(tile))
        for tag in np.unique(tile):
            kk=np.flatnonzero(tile==tag);A[np.ix_(kk,kk)]-=1/len(kk)
        means.append(np.sum(A*(np.outer(m,m)+C))/len(tile))
    return np.array(means)


def known():
    rng=np.random.default_rng(884797);h=rng.normal(size=(4,4,2));tile=np.repeat([0,1],[3,7]);g=np.exp(.3*rng.normal(size=(len(tile)*3,4)))
    R=covariance(h);P=R[0];actual=conditional_mean(g,R,tile,P,3);expected=white_trace(h,g,tile,3)
    error=float(abs(actual['total']-expected).max());assert error<1e-12
    constant=np.full_like(g,1.7);unit=conditional_mean(np.ones_like(g),R,tile,P,3);scaled=conditional_mean(constant,R,tile,P,3)
    scaling=float(abs(scaled['total']-unit['total']*1.7**4).max());assert scaling<1e-12 and abs(scaled['path']).max()<1e-20
    zero=conditional_mean(np.zeros_like(g),R,tile,P,3);assert not np.any(zero['total'])
    signs=np.array([-1,1,-1,1]);signed=conditional_mean(g,covariance(h*signs[None,:,None]),tile,P,3);assert abs(signed['total']-actual['total']).max()<1e-12
    delayed=np.zeros((4,4,4))
    for i in range(4):delayed[i,i,i]=1+i*.3
    rd=covariance(delayed);independent=conditional_mean(g,rd,tile,rd[0],3);independent_error=float(abs(independent['total']-white_trace(delayed,g,tile,3)).max());assert independent_error<1e-12
    node,w=hermgauss(5);z=np.stack(np.meshgrid(node*np.sqrt(2),node*np.sqrt(2),node*np.sqrt(2),indexing='ij'),axis=-1).reshape(-1,3);weights=np.einsum('i,j,k->ijk',w,w,w).ravel()/np.pi**1.5
    hh=np.array([1.,.3])[:,None,None]*np.array([1.,-.7,.3,-1.2])[None,:,None];gg=np.array([[.7,.9,1.3,.8],[1.4,.6,.8,1.1]])
    rr=covariance(hh);quad=[]
    for i in range(4):
        c=np.column_stack((z[:,0]*hh[1,i,0]+z[:,1]*hh[0,i,0],z[:,1]*hh[1,i,0]+z[:,2]*hh[0,i,0]))
        e=(c*gg[:,i])**2/rr[0,i];stat=np.mean((e-e.mean(axis=1)[:,None])**2,axis=1);quad.append(weights@stat)
    small=conditional_mean(gg,rr,np.zeros(2,int),rr[0],1);quad_error=float(abs(small['total']-quad).max());assert quad_error<1e-12
    rejected=0
    for bad_g,bad_p in [(g[:-1],P),(g,np.zeros(4))]:
        try:conditional_mean(bad_g,R,tile,bad_p,3)
        except ValueError:rejected+=1
    assert rejected==2
    return dict(full_white_matrix_error=error,constant_gain_fourth_scaling_error=scaling,independent_delayed_error=independent_error,
        exact_Gaussian_quadrature_error=quad_error,zero_gain=True,signed_carrier_coefficients=True,invalid_inputs_rejected=rejected),dict(impulse=h,gain=g,tile=tile,covariance=R,
        expected=expected,**actual,small_impulse=hh,small_gain=gg,small_expected=np.array(quad))
