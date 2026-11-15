"""Independent SciPy-supported frames and direct real OSC matrices."""
import numpy as np
from scipy import linalg
from observer_complete_v1.audit_oracle import full_frame,hats,curvature
from observer_frequency_v1.reduced_oracle import carrier_table


def metric(audio,root):
    rows,cover=full_frame(audio)
    starts=np.arange(-3840,len(audio),256);keep=(starts>=0)&(starts+4096<=len(audio))
    amplitude=np.sqrt(len(audio)/(256*keep.sum()));supported=rows[keep]*amplitude
    freq=np.arange(2049)*root/4;edges=[0,3000,6000,8000,10000,14000,np.inf]
    power=[];ids=np.zeros(2049,int)
    for j in range(6):
        selected=(freq>=edges[j])&(freq<edges[j+1]);ids[selected]=j
        power.append(float(np.sum(supported[:,selected].real**2+supported[:,selected].imag**2)/audio.size))
    power=np.array(power);global_power=float(np.mean(audio**2))
    weights=np.ones(2049) if not global_power else 1/np.sqrt(np.maximum(power[ids],global_power*1e-8))
    coverage=np.zeros(len(audio));w=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    for start in starts[keep]:coverage[start:start+4096]+=w*w
    return dict(rows=supported,full_coverage=cover,keep=keep,weights=weights,band_power=power,
        amplitude=amplitude,time_coverage=amplitude**2*coverage/cover,global_power=global_power,
        sigma=np.sqrt(global_power) if global_power else 1.,floor_active=power<global_power*1e-8)


def matrices(positions,orders,scale,audio,profile=None):
    if profile is None:profile=metric(audio,64.)
    N,C=audio.shape;M,H=len(positions),len(orders);size=M*H*C
    basis=hats(positions,N);carrier=carrier_table(tuple(int(k) for k in orders))[np.arange(N)%1024]
    Phi=np.zeros((N*C,2*size))
    for m in range(M):
        for h in range(H):
            for c in range(C):
                j=(m*H+h)*C+c
                Phi[c::C,j]=basis[m]*carrier[:,h].real*scale[h,0]
                Phi[c::C,size+j]=-basis[m]*carrier[:,h].imag*scale[h,0]
    starts=np.arange(0,N-4096+1,256);w=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
    spectral=np.empty((len(starts),2049,C,2*size),complex);weights=np.r_[1.,np.full(2047,np.sqrt(2.)),1.]
    for j,start in enumerate(starts):
        for c in range(C):
            segment=Phi[c::C][start:start+4096]*w[:,None]/np.sqrt(6.)
            spectral[j,:,c]=np.fft.rfft(segment,axis=0)*weights[:,None]/64
    spectral*=profile['amplitude']*profile['weights'][None,:,None,None]
    data=np.vstack((Phi/profile['sigma'],spectral.real.reshape(-1,2*size),spectral.imag.reshape(-1,2*size)))
    target=profile['rows']*profile['weights'][None,:,None]
    b=np.r_[audio.ravel()/profile['sigma'],target.real.ravel(),target.imag.ravel()]
    D=curvature(positions);reg=np.sqrt(.001)*linalg.block_diag(np.kron(D,np.eye(H*C)),np.kron(D,np.eye(H*C)))
    tail=np.vstack((reg,np.sqrt(.000001)*np.eye(2*size)))
    K=.001*D.T@D+.000001*np.eye(M)
    R=linalg.block_diag(np.kron(K,np.eye(H*C)),np.kron(K,np.eye(H*C)))
    return np.vstack((data,tail)),np.r_[b,np.zeros(len(tail))],Phi,R,len(data)


def block_right(positions,orders,scale,profile):
    N=len(profile['time_coverage']);M,H=len(positions),len(orders)
    basis=hats(positions,N);n=np.arange(N);D=curvature(positions)
    K=.001*D.T@D+.000001*np.eye(M);regularizer=linalg.block_diag(K,K);result=[]
    for h,order in enumerate(orders):
        carrier=carrier_table((int(order),))[n%1024,0]
        basis_h=np.column_stack((basis.T*carrier.real[:,None],-basis.T*carrier.imag[:,None]))
        coverage=scale[h,0]**2*(1/profile['sigma']**2+profile['time_coverage']*profile['weights'][4*order]**2)
        gram=regularizer+basis_h.T@(coverage[:,None]*basis_h)
        result.append(linalg.solve_triangular(np.linalg.cholesky(gram).T,np.eye(2*M),lower=False))
    return np.array(result)
