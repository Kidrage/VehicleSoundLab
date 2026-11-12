"""Independent recurrence/PSD/envelope controls for the proposed source kernel."""
import numpy as np
from scipy import signal
from .filters import theory,spectral_matrix_operator
from .envelope import samples
from .voice import render

def run(plan):
    # One explicitly known damped pole pair; full independent recurrence,
    # never fit a model to make this fixture pass.
    radius=.97;theta=2*np.pi*4500/48000;a=np.array([1,-2*radius*np.cos(theta),radius*radius])
    beta=np.zeros(16);beta[0]=.4;beta[9]=.15
    sos=signal.butter(4,[3300,6000],fs=48000,btype='bandpass',output='sos')
    psd,sigma=theory(a,sos,beta,plan)
    model=dict(a=a.tolist(),sigma=sigma,sos=sos.tolist(),envelope=dict(coefficients=beta.tolist()))
    raw=np.random.default_rng(71).normal(size=4096);direct=np.zeros_like(raw)
    for i,v in enumerate(raw):direct[i]=sigma*v-sum(a[k]*direct[i-k] for k in range(1,min(i,len(a)-1)+1))
    expected=signal.lfilter([sigma],a,raw)
    error=float(max(abs(direct-expected)));assert error<plan['checks']['direct_recurrence_error']
    # Analytic response versus a direct trigonometric polynomial.
    f=np.array([100,2000,4500,7000,17000]);w=2*np.pi*f/48000
    _,h=signal.freqz([sigma],a,worN=w)
    direct_h=sigma/np.sum(a[None,:]*np.exp(-1j*w[:,None]*np.arange(len(a))),axis=1)
    response_error=float(max(abs(h-direct_h)));assert response_error<1e-10
    phase=samples(beta,1024);assert abs(np.mean(phase**2)-1)<1e-12
    x=render([model],48000*20,71,plan)[:,0]
    hz,power=signal.welch(x,fs=48000,nperseg=2048,noverlap=1536,detrend=False)
    actual=np.array([power[(hz>=lo)&(hz<hi)].sum()*48000/2048 for lo,hi in plan['bands_hz']])
    predicted=spectral_matrix_operator(psd,plan)
    active=predicted>predicted.max()*1e-3
    db=float(max(abs(10*np.log10(actual[active]/predicted[active]))))
    assert db<plan['checks']['known_theory_power_error_db'],db
    return dict(result='pass',direct_recurrence_error_FS=error,direct_response_error=response_error,
                expected_Welch_maximum_error_db=db,known_pole_radius=radius)
