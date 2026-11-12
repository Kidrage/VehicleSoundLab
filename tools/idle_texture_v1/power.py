"""Expected resonant PSD with arbitrary acoustic pitch, no integer FFT shifts."""
import numpy as np
from scipy import signal
from resonant_detail_v1.envelope import samples
from resonant_detail_v1.filters import spectral_matrix_operator

def theory(model,root,plan):
    n=plan['spectral_grid_frames'];rate=plan['sample_rate']
    hz=np.arange(n)*rate/n
    count=plan['envelope_phase_grid_frames']
    e=np.fft.fft(samples(model['envelope']['coefficients'],count,cycle=count))/count
    orders=np.fft.fftfreq(count)*count;result=np.zeros(n)
    for order,weight in zip(orders,abs(e)**2):
        if weight>1e-18:
            # Evaluate the rational response at the exact shifted frequency.
            # No rounded root, cyclic-bin approximation or PCM period needed.
            _,h=signal.freqz([model['sigma']],model['a'],worN=2*np.pi*(hz-order*root)/rate)
            result+=weight*abs(h)**2/rate
    _,post=signal.sosfreqz(np.asarray(model['sos']),worN=2*np.pi*hz/rate)
    return result*abs(post)**2

def controls(plan):
    root=10.005673871228469;r=.90;angle=2*np.pi*3100/48000
    a=np.array([1,-2*r*np.cos(angle),r*r]);depth=.24
    beta=np.zeros(24);beta[0]=2*depth/(1+depth*depth/2);beta[1]=(depth*depth/2)/(1+depth*depth/2)
    sos=signal.butter(3,[2100,4300],btype='bandpass',fs=48000,output='sos')
    known=dict(a=a.tolist(),sigma=1.,sos=sos.tolist(),envelope=dict(coefficients=beta.tolist()))
    control_plan=dict(plan,bands_hz=[[2200,2800],[2800,3400],[3400,4200]])
    actual=theory(known,root,control_plan)
    hz=np.arange(plan['spectral_grid_frames'])*48000/plan['spectral_grid_frames']
    def ar(f):
        z=np.exp(-2j*np.pi*f/48000)
        return 1/abs(1+a[1]*z+a[2]*z*z)**2/48000
    z=np.exp(-2j*np.pi*hz/48000);post=np.ones(len(hz),complex)
    for b0,b1,b2,a0,a1,a2 in sos:post*=(b0+b1*z+b2*z*z)/(a0+a1*z+a2*z*z)
    expected=(ar(hz)+depth*depth/4*(ar(hz-root)+ar(hz+root)))/(1+depth*depth/2)*abs(post)**2
    relative=float(np.max(abs(actual-expected))/max(expected))
    assert relative<plan['checks']['known_theory_relative_error'],relative
    rng=np.random.default_rng(591207);warm=96000;frames=20*48000
    x=signal.lfilter([1],a,rng.normal(size=warm+frames))
    t=np.arange(-warm,frames)/48000
    x*= (1+depth*np.cos(2*np.pi*root*t))/np.sqrt(1+depth*depth/2)
    x=signal.sosfilt(sos,x)[warm:]
    f,p=signal.welch(x,fs=48000,nperseg=2048,noverlap=1536,detrend=False)
    measured=np.array([p[(f>=lo)&(f<hi)].sum()*48000/2048 for lo,hi in control_plan['bands_hz']])
    prediction=spectral_matrix_operator(actual,control_plan)
    error=float(max(abs(10*np.log10(measured/prediction))))
    assert error<plan['checks']['known_theory_Welch_error_db'],error
    return dict(exact_shift_relative_error=relative,known20s_Welch_error_db=error,
        root_hz=root,period_frames=48000/root,not_integer_period=True)
