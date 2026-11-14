"""Independent scalar-demodulation check of the new aperture measurements."""
import numpy as np
from exterior_clock_v1.warp import carrier_rows


def carrier_diagnostics(audio, orders=(3,5,7)):
    size=4096;starts=np.arange(0,len(audio)-size+1,256)
    # Direct time-domain inner products, independent of the production FFT.
    window=np.hanning(size+1)[:-1];t=np.arange(size)
    result={};maximum=0.
    for order in orders:
        carrier=np.exp(-2j*np.pi*order*t/1024)*window*2/window.sum()
        values=np.array([(audio[start:start+size]*carrier[:,None]).sum(axis=0)*
                         np.exp(-2j*np.pi*order*start/1024) for start in starts])
        centers,expected=carrier_rows(audio,order)
        maximum=max(maximum,float(abs(expected-values).max()))
        magnitude=abs(values);phase=np.unwrap(np.angle(values),axis=0)
        result[str(order)]=dict(centers=centers.tolist(),
            coherence=(abs(values.mean(axis=0))/magnitude.mean(axis=0)).tolist(),
            magnitude=magnitude.tolist(),phase_radians=(phase-phase[0]).tolist())
    assert maximum<1e-12,maximum
    return dict(direct_FFT_maximum_FS=maximum,orders=result)
