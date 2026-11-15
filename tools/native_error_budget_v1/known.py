"""Analytic interpolation and direct all-bin DFT qualification before sources."""
import numpy as np
from .interpolate import reconstruct
from .budget import analyze


def qualify():
    rng = np.random.default_rng(920621)
    x = np.arange(8192)
    query = np.linspace(128.125,8062.875,1201)
    orders = np.array([1,64,128,224,288])
    amplitude = np.array([[.12,.08],[.08,-.09],[.05,.11],[.07,.06],[.08,-.12]])
    phase = np.array([[.1,.3],[.4,-.5],[1.1,2.1],[.9,-1.3],[-.7,.2]])
    def exact(t):
        return np.sum(amplitude[None]*np.cos(2*np.pi*t[:,None,None]*orders[None,:,None]/1024+phase[None]),axis=1)
    signal = exact(x)
    cases = []
    for radius in (32,64,128):
        output = reconstruct(signal,query,radius)
        analytic_error = float(np.max(abs(output-exact(query)))/np.sum(abs(amplitude)))
        assert analytic_error < 2e-5, (radius,analytic_error)
        mono = reconstruct(np.repeat(signal[:,:1],2,axis=1),query,radius)
        assert np.array_equal(mono[:,0],mono[:,1])
        silent = reconstruct(np.column_stack((signal[:,0],np.zeros(len(signal)))),query,radius)
        assert not np.count_nonzero(silent[:,1])
        assert not np.count_nonzero(reconstruct(np.zeros_like(signal),query,radius))
        cases.append(dict(radius=radius,analytic_error_relative_to_coefficient_L1=analytic_error,
                          exact_mono_and_silent_right=True))
    rejects = []
    for name,source,q,radius in (
        ('missing_left_context',signal,np.array([20.]),32),
        ('missing_right_context',signal,np.array([8190.]),32),
        ('nonfinite_query',signal,np.array([np.nan]),32),
        ('nonfinite_audio',signal*np.nan,query,32),
        ('complex_audio',signal.astype(complex),query,32),
        ('undeclared_radius',signal,query,16)):
        try:
            reconstruct(source,q,radius)
        except ValueError:
            rejects.append(name)
        else:
            raise AssertionError('Invalid reconstruction accepted: '+name)
    # Broadband references keep every independently checked band observable;
    # destructive cancellation exercises signed cross terms, not a power floor.
    raw = rng.standard_normal((4608,2))*.1
    a,b = rng.standard_normal((2,4608,2))*.02
    fixtures = (
        ('cancellation',raw,raw+a,raw,raw+b,raw),
        ('independent_LR',raw,raw+a,raw+a+b,raw+2*a+b,raw+2*a+1.5*b),
        ('zero',np.zeros_like(raw),np.zeros_like(raw),np.zeros_like(raw),np.zeros_like(raw),np.zeros_like(raw)))
    dft_checks = []
    for name,*signals in fixtures:
        arrays,info = analyze(*signals)
        columns = arrays['components'].reshape(len(raw),8)
        direct = np.empty((len(arrays['starts']),2049,8),complex)
        window = .5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
        for j,start in enumerate(arrays['starts']):
            segment = columns[start:start+4096]*window[:,None]
            for first in range(0,2049,64):
                bins = np.arange(first,min(first+64,2049))
                matrix = np.exp(-2j*np.pi*bins[:,None]*np.arange(4096)[None]/4096)
                direct[j,first:first+len(bins)] = matrix@segment
        errors = []
        groups = np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*48000/4096,side='right')
        weights = np.r_[1.,np.full(2047,2.),1.]
        for band in range(6):
            selected = groups==band
            X = direct[:,selected].reshape(-1,8)
            w = np.tile(weights[selected],len(direct))
            wanted = (X.T*w)@X.conj()
            scale = float(np.max(abs(wanted)))
            error = float(np.max(abs(arrays['band_joint_Gram'][band]-wanted)))
            assert (error/scale if scale else error)<2e-11
            errors.append(error/scale if scale else error)
        if name=='cancellation':
            assert not np.count_nonzero(arrays['total_error'])
            assert np.any(arrays['band_component_signed_cross_power']<0)
            assert np.max(arrays['band_component_auto_power'])>1.
        scale = np.sum(arrays['band_component_auto_power'],axis=1)+np.sum(abs(arrays['band_component_signed_cross_power']),axis=(1,2))
        difference = abs(arrays['band_recovered_error_power']-arrays['band_error_power'])
        relative = np.divide(difference,scale,out=np.zeros_like(difference),where=scale>0)
        assert np.max(relative)<2e-12 and info['closure_max_FS']<2e-15
        dft_checks.append(dict(name=name,all_band_joint_Gram_DFT_relative_error=errors,
                              signed_power_equation_relative_error=float(np.max(relative))))
    return dict(interpolation=cases,invalid_rejections=rejects,direct_DFT=dft_checks,
                analytic_amplitude_gate=2e-5,DFT_Gram_gate=2e-11,signed_power_equation_gate=2e-12,
                all_qualified=True)
