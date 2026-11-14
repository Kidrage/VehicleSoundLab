"""Joint real coefficient factors retain covariance and pseudo-covariance."""
import numpy as np


def root(moment):
    eig,v=np.linalg.eigh(moment);scale=float(eig.max())
    if eig.min() < -1e-10*scale:raise ValueError('Outer-product moment unexpectedly indefinite')
    factor=(v*np.sqrt(np.maximum(eig,0.)))@v.T
    error=float(np.linalg.norm(factor@factor.T-moment)/np.linalg.norm(moment))
    if error>1e-10:raise ValueError('Moment factorization failed')
    return factor,dict(minimum_eigenvalue=float(eig.min()),maximum_eigenvalue=scale,
        roundoff_negative_count=int((eig<0).sum()),relative_factor_error=error)


def independent_blocks(moment):
    m=len(moment)//2;out=np.zeros_like(moment)
    for j in range(m):
        ids=[j,j+m];out[np.ix_(ids,ids)]=moment[np.ix_(ids,ids)]
    return out


def compile_model(coefficients,groups,target_variance):
    n,m=coefficients.shape;real=np.column_stack((coefficients.real,coefficients.imag))
    raw=real.T@real/n;scale=np.ones(2*m)
    for b in range(4):
        ids=np.flatnonzero(np.asarray(groups)==b);indices=np.r_[ids,ids+m]
        power=float(np.trace(raw[np.ix_(indices,indices)])/2)
        if power<=0:raise ValueError('Missing source coefficient power')
        scale[indices]=np.sqrt(target_variance[b]/power)
    moment=raw*scale[:,None]*scale[None,:]
    joint,jinfo=root(moment);blocks=independent_blocks(moment);separate,sinfo=root(blocks)
    return dict(moment=moment,independent_moment=blocks,joint_factor=joint,independent_factor=separate,
        row_scale=scale),dict(joint=jinfo,independent=sinfo,frames=n,carriers=m,
        target_variance=target_variance,per_band_row_scale=[float(scale[np.flatnonzero(np.asarray(groups)==b)[0]]) for b in range(4)])


def known():
    # Exact four-sign ensemble, with a cross-carrier contribution to sound power.
    u=np.array([[-1.,-1.],[-1.,1.],[1.,-1.],[1.,1.]])
    c=u@np.array([[.8,.3,.1,-.2],[.1,-.4,.5,.2]])
    r=c.T@c/len(c);factor,info=root(r)
    angle=.73*np.array([2.,3.]);a=np.r_[np.cos(angle),-np.sin(angle)]
    expected=float(np.mean((c@a)**2));actual=float(np.sum((factor.T@a)**2))
    assert abs(expected-actual)<1e-13
    block=independent_blocks(r);assert abs(float(a@block@a)-expected)>1e-3
    # Rotating the phase origin rotates coefficients; waveform ensemble stays identical.
    z=c[:,:2]+1j*c[:,2:];delta=.37*np.array([2.,3.]);changed=z*np.exp(-1j*delta)
    waveform=(z*np.exp(1j*angle)).real.sum(axis=1)
    other=(changed*np.exp(1j*(angle+delta))).real.sum(axis=1)
    error=float(abs(waveform-other).max());assert error<1e-14
    return dict(exact_ensemble_power_error=abs(expected-actual),phase_origin_error=error,
        independent_control_keeps_every_2x2_block=True,factor=info)
