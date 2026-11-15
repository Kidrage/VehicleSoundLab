"""Independent per-harmonic OSC, SciPy observer and regularized residual."""
import numpy as np
from scipy import signal
from observer_forward_v1.audit_oracle import adjoint
from circular_phase_lift_v1.audit_oracle import statistics


def render_groups(nodes,positions,root,edges,frames):
    n=np.arange(frames);group=np.zeros((frames,len(edges)-1,nodes.shape[-1]))
    for h in range(nodes.shape[1]):
        tag=next(i for i in range(len(edges)-1) if edges[i]<=(h+1)*root<edges[i+1])
        carrier=np.exp(2j*np.pi*(h+1)*n/1024)
        for c in range(nodes.shape[-1]):
            envelope=np.interp(n,positions,nodes[:,h,c].real)+1j*np.interp(n,positions,nodes[:,h,c].imag)
            group[:,tag,c]+=(envelope*carrier).real
    return group


def observe(group,root,bands):
    N,G,C=group.shape;flat=group.reshape(N,G*C)
    hz,_,z=signal.stft(flat.T,fs=1024*root,window='hann',nperseg=4096,noverlap=3840,boundary=None,padded=False)
    starts=np.arange(0,N-4096+1,256);orders=np.arange(1,289);total=z.reshape(G,C,len(hz),len(starts)).sum(axis=0)
    coefficients=np.moveaxis(total[:,4*orders],(0,1,2),(2,1,0))*2
    coefficients*=np.exp(-2j*np.pi*starts[:,None]*orders[None,:]/1024)[:,:,None]
    weight=np.full(len(hz),4/3);weight[[0,-1]]=2/3
    line=[];broad=[];power=[];cross=[];bp=[];bc=[]
    for lo,hi in bands:
        index=4*orders[(orders*root>=lo)&(orders*root<hi)];mask=(hz>=lo)&(hz<hi)
        line.append(np.einsum('ikt,jkt->tij',z[:,index],z[:,index].conj(),optimize=False)*2)
        broad.append(np.einsum('ikt,jkt,k->tij',z[:,mask],z[:,mask].conj(),weight[mask],optimize=False))
        power.append((abs(total[:,index])**2).sum(axis=1).T*2);cross.append((total[0,index]*total[1,index].conj()).sum(axis=0)*2)
        bp.append((abs(total[:,mask])**2*weight[mask,None]).sum(axis=1).T);bc.append((total[0,mask]*total[1,mask].conj()*weight[mask,None]).sum(axis=0))
    w=signal.windows.hann(4096,sym=False)
    return dict(coefficients=coefficients,power=np.concatenate(power,axis=1),cross=np.stack(cross,axis=1),
                broadband_power=np.concatenate(bp,axis=1),broadband_cross=np.stack(bc,axis=1),
                line_Gram=np.stack(line,axis=1),broad_Gram=np.stack(broad,axis=1),
                all_frequency_Gram=np.einsum('ikt,jkt,k->tij',z,z.conj(),weight,optimize=False),
                time_energy_Gram=np.array([(flat[s:s+4096]*w[:,None]).T@(flat[s:s+4096]*w[:,None])/np.dot(w,w) for s in starts]))


def objective_gradient(nodes,positions,scale,target,observed,alpha=1e-3,beta=1e-6):
    q=nodes/scale[None];M=len(q);D=np.zeros((M-2,M))
    for j in range(M-2):
        left,right=np.diff(positions[j:j+3]);factor=2*256**2/(left+right)
        D[j,j]=factor/left;D[j,j+2]=factor/right;D[j,j+1]=-factor/left-factor/right
    d=(D@q.reshape(M,-1)).reshape((M-2,)+q.shape[1:]);res=(observed-target)/scale[None]
    penalty=(D.T@d.reshape(M-2,-1)).reshape(q.shape)
    frames=int(positions[-1]+1);orders=np.arange(1,q.shape[1]+1)
    g=adjoint((observed-target)/scale[None]**2,positions,orders,orders,frames)*scale[None]+alpha*penalty+beta*q
    initial=adjoint(target/scale[None]**2,positions,orders,orders,frames)*scale[None]
    value=float(np.vdot(res,res).real+alpha*np.vdot(d,d).real+beta*np.vdot(q,q).real)
    relative=float(np.linalg.norm(g)/max(np.linalg.norm(initial),1e-24))
    return value,relative,float(np.linalg.norm(g)/beta)
