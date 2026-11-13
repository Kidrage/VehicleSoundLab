"""Lag orientation and broad non-engine association controls."""
import numpy as np
from .observe import curves,PAIRS


def direct(x,lags):
    full=np.var(x,axis=0);out=[]
    for b,c in PAIRS:
        row=[]
        for lag in lags:
            first=max(0,-lag);last=min(len(x),len(x)-lag)
            u=x[first:last,b];v=x[first+lag:last+lag,c]
            u=u-u.mean();v=v-v.mean()
            K=np.mean(u*u*v*v)-np.mean(u*u)*np.mean(v*v)-2*np.mean(u*v)**2
            row.append(K/full[b]/full[c])
        out.append(row)
    return np.array(out)


def run(folder,lags):
    rng=np.random.default_rng(149921)
    n=8192;q=rng.standard_normal(n)*(rng.random(n)<.035)/np.sqrt(.035)
    shifted=np.zeros(n);shifted[96:]=q[:-96]
    delayed=np.column_stack((q,shifted,rng.standard_normal(n),rng.standard_normal(n)))
    nslow=144000;t=np.arange(nslow)/48000
    slow=rng.standard_normal((nslow,4))*(1+.8*np.cos(2*np.pi*3*t))[:,None]
    results={}
    for name,x in [('delayed_common',delayed),('slow_common_amplitude',slow)]:
        measured=curves(x,lags);oracle=direct(x,lags)
        error=float(abs(measured['normalized']-oracle).max())
        assert error<1e-9,(name,error)
        scaled=curves(x*np.array([-.17,2.,.6,-3.]),lags)
        assert np.allclose(scaled['normalized'],measured['normalized'],atol=1e-9)
        for row,(b,c) in enumerate(PAIRS):
            if b==c:assert np.allclose(measured['normalized'][row],measured['normalized'][row,::-1],atol=1e-9)
        np.savez_compressed(folder/(name+'.npz'),audio=x,lags=lags,**measured)
        results[name]=dict(maximum_direct_error=error,frames=len(x))
    peak=int(lags[np.argmax(curves(delayed,lags)['normalized'][PAIRS.index((0,1))])])
    assert peak==96,peak
    results['delayed_common']['observed_peak_frames']=peak
    # Broad common gain on Gaussian carriers is not evidence of an engine source.
    values=curves(slow,lags)['normalized'][PAIRS.index((0,1))]
    assert values[0]>0 and values[-1]>0
    results['slow_common_amplitude']['edge_Q']=[float(values[0]),float(values[-1])]
    return results
