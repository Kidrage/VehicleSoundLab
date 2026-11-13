"""Continuous known mixtures, isolated AM/FM, and one band-limited mono noise."""
import numpy as np


def make(case, plan):
    rate,n,count = [plan[k] for k in ['sample_rate','frames','windows']]
    t = np.arange(n*count)/rate
    base = np.asarray(plan['base_hz'])
    moving = np.asarray(plan['moving'])
    amplitude = np.asarray(plan['amplitude_L'])
    phase0 = np.asarray(plan['phase_radians'])
    q = base*moving*plan['linear_slope_per_second']
    if case=='bandlimited_mono_noise':
        noise=plan['noise']
        raw=np.random.default_rng(noise['seed']).normal(size=len(t))
        cells=np.fft.rfft(raw)
        hz=np.fft.rfftfreq(len(t),1/rate)
        cells[(hz<noise['band_hz'][0])|(hz>=noise['band_hz'][1])]=0
        left=np.fft.irfft(cells,n=len(t))
        left*=noise['rms']/np.sqrt(np.mean(left**2))
        return np.column_stack((left,noise['right_gain']*left)),[]
    am=case in ['am_only','am_fm']
    fm=case in ['fm_only','am_fm']
    omega=2*np.pi*plan['FM']['modulation_hz']
    dev=(base/plan['FM']['reference_hz'])*moving*plan['FM']['deviation_at_reference_hz']*fm
    cycles=t[:,None]*base+.5*t[:,None]**2*q-np.cos(omega*t[:,None])*dev/omega
    phase=2*np.pi*cycles+phase0
    gain=1+am*plan['AM']['depth']*np.sin(2*np.pi*plan['AM']['frequency_hz']*t)
    audio=np.column_stack((np.cos(phase)@amplitude,
        np.cos(phase+plan['right_phase_radians'])@(amplitude*plan['right_gain'])))*gain[:,None]
    truth=[]
    for i in range(count):
        center=(i+.5)*n/rate
        f=base+q*center+dev*np.sin(omega*center)
        slope=q+dev*omega*np.cos(omega*center)
        theta=2*np.pi*(base*center+.5*q*center**2-dev*np.cos(omega*center)/omega)+phase0
        g=1+am*plan['AM']['depth']*np.sin(2*np.pi*plan['AM']['frequency_hz']*center)
        lines=[dict(index=k,frequency_hz=float(f[k]),chirp_hz_per_second=float(slope[k]),
                    phase_at_midpoint_LR=[float(theta[k]),float(theta[k]+plan['right_phase_radians'])],
                    amplitude_LR=[float(g*amplitude[k]),float(g*amplitude[k]*plan['right_gain'])],
                    eligible=True) for k in range(len(base))]
        truth.append(dict(success=True,lines=lines,diagnostic_only=True))
    return audio,truth
