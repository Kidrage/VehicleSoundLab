"""Joint dry-bus spectra with signed DNA/other interaction kept explicitly."""
import numpy as np


def measure(canonical,layers,spec):
    n,hop,size,rate=[spec[k] for k in ['window_samples','hop_samples','fft_samples','rate']]
    assert canonical.shape==(len(layers),2) and layers.shape[1:]==(6,2)
    starts=np.arange(0,len(layers)-n+1,hop);window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    dna=layers[:,0];other=layers[:,1:].sum(axis=1)
    signals=np.column_stack([dna,other,canonical])
    ft=np.fft.rfft(signals[starts[:,None]+np.arange(n)]*window[None,:,None],n=size,axis=1)
    hz=np.arange(size//2+1)*rate/size;weight=np.full(len(hz),2/(size*np.dot(window,window)));weight[[0,-1]]*=.5
    joint=[]
    for low,high in spec['bands_hz']:
        keep=(hz>=low)&(hz<high);v=ft[:,keep]
        joint.append(np.einsum('wfi,wfj,f->wij',v,v.conj(),weight[keep],optimize=True))
    joint=np.stack(joint,axis=1)
    P_dna,P_other,P_canonical=joint[:,:,:2,:2],joint[:,:,2:4,2:4],joint[:,:,4:,4:]
    cross=joint[:,:,:2,2:4];signed=cross+cross.swapaxes(-1,-2).conj()
    return dict(window_starts=starts,P_dna=P_dna,P_other=P_other,P_canonical=P_canonical,
                cross_DNA_other=cross,signed_cross=signed,
                P_tap_sum=P_dna+P_other+signed,
                signed_cross_eigenvalues=np.linalg.eigvalsh(signed),
                maximum_canonical_tap_rounding_difference_FS=float(abs(canonical-dna-other).max()))
