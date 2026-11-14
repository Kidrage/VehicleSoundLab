"""Local response branches share excitation; full Gram retains their correlation."""
import numpy as np
from scipy import signal


def partition(frequencies, centers):
    frequencies, centers = np.asarray(frequencies), np.asarray(centers)
    if np.any(np.diff(centers)<=0):raise ValueError('Increasing cell centers required')
    masks = np.zeros((len(centers),len(frequencies)))
    masks[0,frequencies<=centers[0]] = 1
    masks[-1,frequencies>=centers[-1]] = 1
    for j in range(len(centers)-1):
        use=(frequencies>centers[j])&(frequencies<centers[j+1])
        u=(frequencies[use]-centers[j])/(centers[j+1]-centers[j])
        weights=.5*(1+np.cos(np.pi*u))
        masks[j,use],masks[j+1,use]=weights,1-weights
        masks[j,frequencies==centers[j]]=1
    if np.max(abs(masks.sum(axis=0)-1))>1e-14:raise ValueError('Incomplete response partition')
    return masks


def compile_bank(taps, centers):
    count,delay=32768,16384
    original=np.zeros(count);original[delay:delay+len(taps)]=taps
    spectrum=np.fft.rfft(original)
    masks=partition(np.fft.rfftfreq(count,1/48000),centers)
    branches=np.fft.irfft(masks*spectrum[None,:],n=count,axis=1)
    gram=branches@branches.T;reference=float(np.dot(taps,taps))
    error=float(abs(branches.sum(axis=0)-original).max())
    if error>1e-13:raise ValueError('Branch sum does not reproduce original kernel')
    if np.linalg.eigvalsh(gram).min()<=0:raise ValueError('Positive branch Gram required')
    return dict(taps=branches,gram=gram,reference_variance=reference,delay_frames=delay,
                reconstruction_error=error,centers_hz=np.asarray(centers))


def gain(probabilities,prior,amount,gram,reference):
    raw=np.exp(amount*.5*(np.log(probabilities)-np.log(prior)))
    variance=np.einsum('ti,ij,tj->t',raw,gram,raw)
    if np.any(variance<=0) or not np.isfinite(variance).all():raise ValueError('Invalid full-Gram variance')
    return raw*np.sqrt(reference/variance)[:,None]


def known():
    taps=np.array([[.3,.1,-.2,.1],[.1,-.1,.4,.2],[-.2,.3,.1,.1]])
    gram=taps@taps.T;reference=float(np.dot(taps.sum(axis=0),taps.sum(axis=0)))
    probability=np.array([[.1,.3,.6],[.4,.4,.2]])
    g=gain(probability,[.2,.3,.5],1.,gram,reference)
    actual=np.sum((g@taps)**2,axis=1)
    error=float(abs(actual-reference).max());assert error<1e-14
    assert max(abs(np.sum(g*g*np.diag(gram),axis=1)-reference))>1e-3
    bank=compile_bank(signal.firwin(129,.24),[1300,1500,1700,1900])
    assert bank['reconstruction_error']<1e-14
    return dict(correlated_branch_variance_error=error,kernel_partition_error=bank['reconstruction_error'],
                diagonal_only_normalization_rejected=True)
