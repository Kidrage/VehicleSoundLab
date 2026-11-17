"""Sparse controllable chirplet score; an acoustic representation, not RPM ID.

Each atom has a finite Hann support, a linear frequency motion, and constant
L/R complex amplitude. No source waveform or per-frame phase table is exported.
"""
import numpy as np
from scipy import signal

RATE=48000

def window_basis(n,start,length,hz,slew):
    t=np.arange(length)/RATE
    phase=2*np.pi*(hz*t+.5*slew*t*t)
    w=signal.windows.hann(length,sym=False)
    out=np.zeros((n,2));out[start:start+length,0]=w*np.cos(phase);out[start:start+length,1]=w*np.sin(phase)
    return out

def fit(x,count=40,*,lengths=(2048,4096,8192),slews=(-4000.,-2000.,0.,2000.,4000.),hop=768,hz_range=(100.,5000.)):
    n=len(x);residual=x.copy();atoms=[];basis=[]
    # Sparse geometric score only. Neither a narrow peak nor a successful
    # projection identifies a mechanical part or a persistent oscillator.
    for iteration in range(count):
        best=None
        for length in lengths:
            if length>n:continue
            starts=np.arange(0,n-length+1,hop)
            rows=np.stack([residual[s:s+length] for s in starts])
            t=np.arange(length)/RATE;w=signal.windows.hann(length,sym=False)
            for slew in slews:
                z=np.fft.fft(rows*w[None,:,None]*np.exp(-1j*np.pi*slew*t*t)[None,:,None],axis=1)
                frequencies=np.fft.fftfreq(length,1/RATE)
                selected=(frequencies>=hz_range[0])&(frequencies<hz_range[1])&(frequencies+slew*(length/RATE)>max(40,hz_range[0]-.2*hz_range[0]))&(frequencies+slew*(length/RATE)<hz_range[1]*1.2)
                power=np.sum(abs(z[:,selected])**2,axis=2)/np.dot(w,w)
                i,j=np.unravel_index(np.argmax(power),power.shape);score=float(power[i,j])
                if best is None or score>best[0]:best=(score,int(starts[i]),length,float(frequencies[selected][j]),slew)
        if best is None:break
        score,start,length,hz,slew=best
        if score<np.sum(x*x)*1e-5:break
        b=window_basis(n,start,length,hz,slew)
        coef=np.linalg.lstsq(b[start:start+length],residual[start:start+length],rcond=None)[0]
        residual-=b@coef;atoms.append(dict(start_frame=start,frames=length,hz=hz,slew_hz_per_second=slew));basis.extend([b[:,0],b[:,1]])
    design=np.column_stack(basis)
    coef=np.linalg.lstsq(design,x,rcond=1e-8)[0]
    core=design@coef;result=[]
    for i,row in enumerate(atoms):
        c,s=coef[2*i:2*i+2]
        amplitude=np.hypot(c,s);phase=np.arctan2(-s,c)
        result.append(dict(**row,amplitude=amplitude.tolist(),phase=phase.tolist()))
    return result,core,x-core

def render(atoms,frames):
    y=np.zeros((frames,2))
    for row in atoms:
        b=window_basis(frames,row['start_frame'],row['frames'],row['hz'],row['slew_hz_per_second'])
        amp=np.array(row['amplitude']);phase=np.array(row['phase'])
        y+=b@np.stack([amp*np.cos(phase),-amp*np.sin(phase)])
    return y

def known():
    n=12288
    expected=[dict(start_frame=1536,frames=4096,hz=750.,slew_hz_per_second=2000.,amplitude=[.3,.2],phase=[.2,.7]),
              dict(start_frame=6144,frames=4096,hz=1500.,slew_hz_per_second=-2000.,amplitude=[.1,.15],phase=[.1,-.3])]
    x=render(expected,n);a,core,left=fit(x,4)
    error=float(np.max(abs(render(a,n)-core)))
    assert error<1e-12
    ratio=float(np.sum(left*left)/np.sum(x*x));assert ratio<.03,ratio
    return dict(synthetic_reconstruction_error=error,synthetic_remaining_energy_ratio=ratio,physical_source_classifier=False)
