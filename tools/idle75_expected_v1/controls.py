"""Small independent finite-white and Gaussian controls, without source audio."""
import numpy as np
from numpy.polynomial.hermite import hermgauss
from idle75_expected_v1.kernel import covariance,gain_covariance


def explicit_white(model,times,clock):
    """Build every white-input coefficient directly, including full FIR history."""
    h=np.array(model['taps']);q=np.array(times)*model['node_rate'];p=q*clock;k=np.floor(p).astype(int);u=p-k
    w=np.array([-.5*u+u*u-.5*u**3,1-2.5*u*u+1.5*u**3,.5*u+2*u*u-1.5*u**3,-.5*u*u+.5*u**3]).T
    dw=np.array([-.5+2*u-1.5*u*u,-5*u+4.5*u*u,.5+4*u-4.5*u*u,-u+1.5*u*u]).T*q[:,None]
    first=int(k.min()-len(h)+1);last=int(k.max()+3);count=last-first+1
    F=np.zeros((len(times),count,h.shape[1]));D=F.copy()
    for t in range(len(times)):
        for i in range(4):
            indices=k[t]+i-np.arange(len(h))-first
            F[t,indices]+=w[t,i]*h;D[t,indices]+=dw[t,i]*h
    F=F.reshape(len(times),-1);D=D.reshape(len(times),-1)
    v=np.sum(F*F,axis=1);dv=2*np.sum(F*D,axis=1);scale=np.sqrt(model['variance']/v)
    D=scale[:,None]*(D-.5*F*(dv/v)[:,None]);F*=scale[:,None]
    return F@F.T,D@F.T+F@D.T


def qualify(model,points):
    # Include integer node seams, both sides of zero and arbitrary fractions.
    times=np.r_[np.arange(-12,12)/50,np.array([-.0137,-.0001,.00017,.00321,.00777,.01337,.03111,.07123,
        .121,.199,.271,.333,.447,.512,.613,.721,.853,.927,1.013,1.127,1.331,1.571,1.733,1.971])]
    assert len(times)==48
    nodes,weight=hermgauss(9);nodes*=np.sqrt(2);weight/=np.sqrt(np.pi)
    rows=[]
    for p in points:
        c,dc=covariance(model,times,p[0]);independent,dindependent=explicit_white(model,times,p[0])
        error=float(abs(c-independent).max());de=float(abs(dc-dindependent).max())
        assert error<1e-12 and de<1e-10
        cg,dclock,ds,mean,dmean=gain_covariance(model,times,p)
        quadrature_error=[]
        for i,j in [(0,0),(3,4),(12,31),(20,23),(36,47)]:
            small=np.array([[c[i,i],c[i,j]],[c[j,i],c[j,j]]]);e,U=np.linalg.eigh(small)
            assert e.min()>-1e-12
            normal=np.stack(np.meshgrid(nodes,nodes,indexing='ij'),axis=-1)@(U*np.sqrt(np.maximum(e,0))).T
            g=np.exp(p[1]*normal-p[1]**2*model['variance']);W=weight[:,None]*weight[None,:]
            cov=float(np.sum(W*g[:,:,0]*g[:,:,1])-np.sum(W*g[:,:,0])*np.sum(W*g[:,:,1]))
            quadrature_error.append(abs(cov-cg[i,j]))
        single=np.exp(p[1]*np.sqrt(model['variance'])*nodes-p[1]**2*model['variance'])
        e2=float(abs(weight@(single**2)-1));eg=float(abs(weight@single-mean))
        assert max(quadrature_error)<1e-10 and e2<1e-10 and eg<1e-12
        # Independent scalar differentiation of the closed form, away from seams.
        step=1e-6;v=model['variance'];plus=np.exp((p[1]+step)**2*(independent-v))-np.exp(-(p[1]+step)**2*v)
        minus=np.exp((p[1]-step)**2*(independent-v))-np.exp(-(p[1]-step)**2*v)
        derror=float(abs((plus-minus)/(2*step)-ds).max());assert derror<1e-9
        rows.append(dict(parameters=p,covariance_error=error,clock_derivative_error=de,
            gain_quadrature_error=max(quadrature_error),E_gain_square_error=e2,E_gain_error=eg,strength_derivative_error=derror,
            minimum_covariance_eigenvalue=float(np.linalg.eigvalsh(cg).min())))
    return rows
