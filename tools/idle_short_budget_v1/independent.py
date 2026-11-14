"""Audit-only native QR and scalar periodogram observations; no production imports."""
import numpy as np
from scipy import signal,linalg,fft


def measured(audio,frequencies):
    n=len(audio);multiplier=np.zeros(n);multiplier[0]=multiplier[n//2]=1;multiplier[1:n//2]=2;out=[]
    for hz in np.array(frequencies)[[1,2,4]]:
        sos=signal.iirfilter(4,[hz-10,hz+10],btype='bandpass',ftype='butter',fs=48000,output='sos')
        y=signal.sosfiltfilt(sos,audio);z=fft.ifft(fft.fft(y)*multiplier);out.append(z/abs(z))
    return np.column_stack(out)


def design(frames,freq,z):
    A=np.ones((frames,27));t=np.arange(frames)/48000
    for j,hz in enumerate(freq):
        v=z[:,[1,2,4].index(j)] if j in [1,2,4] else np.exp(2j*np.pi*hz*t)
        A[:,j]=v.real;A[:,j+13]=v.imag
    return A


def coefficient(buses,A,ms):
    n=int(ms*48);w=np.sqrt(np.hanning(n+1)[:-1]);out=[]
    for centre in 16800+np.arange(116)*960:
        start=centre-n//2;Q,R=np.linalg.qr(A[start:start+n]*w[:,None],mode='reduced')
        b=linalg.solve_triangular(R,Q.T@(buses[start:start+n]*w[:,None]))
        out.append((b[:13]-1j*b[13:26]).T)
    return np.array(out)


def project(buses,A):
    lo,hi=12000,len(buses)-12000;w=np.sqrt(np.hanning(hi-lo+1)[:-1]);Q,R=np.linalg.qr(A[lo:hi]*w[:,None],mode='reduced')
    beta=linalg.solve_triangular(R,Q.T@(buses[lo:hi]*w[:,None]))
    return buses-A@beta,beta


def covariance(left,right):
    left=left-left.mean(axis=0);right=right-right.mean(axis=0);out=[]
    for lag in range(-25,26):
        indices=np.arange(max(0,-lag),min(len(left),len(left)-lag))
        out.append(np.einsum('ti,tj->ij',left[indices],right[indices+lag])/len(indices))
    return np.array(out)


def spectral(buses,residual,z):
    values=[buses[12000:-12000],residual[12000:-12000],residual[12000:-12000]*z[12000:-12000,0,None].conj()]
    psd=[];cross=[]
    for x in values:
        n=len(x);window=np.hanning(n+1)[:-1]
        f,p=signal.periodogram(x,fs=48000,window=window,detrend=False,axis=0,return_onesided=False,scaling='density')
        psd.append(p*48000/n)
        if x.shape[1]==3:
            _,c=signal.csd(x[:,1],x[:,2],fs=48000,window=window,nperseg=n,noverlap=0,detrend=False,return_onesided=False,scaling='density')
            cross.append(2*c.real*48000/n)
    masks=[(abs(f)>=a)&(abs(f)<b) for a,b in [[0,3],[3,8],[8,15]]];low=(abs(f)>=30)&(abs(f)<120)
    result=dict(raw30_120=psd[0][low].sum(axis=0),residual30_120=psd[1][low].sum(axis=0),baseband_power=np.array([psd[2][mask].sum(axis=0) for mask in masks]))
    if buses.shape[1]==3:result.update(raw30_120_cross=np.array(cross[0][low].sum()),residual30_120_cross=np.array(cross[1][low].sum()),baseband_cross=np.array([cross[2][mask].sum() for mask in masks]))
    return result
