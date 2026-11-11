"""Known common gain, colour, stationary and pitch confounds, before recordings."""
import numpy as np
from .features import DB, band_power, decompose, scalar_power_check


def run(plan, save):
    rate=plan['sample_rate'];t=np.arange(4*rate)/rate
    centers=np.array([round((lo+hi)/2*plan['size']/rate)*rate/plan['size'] for lo,hi in plan['bands']])
    phase=2*np.pi*t[:,None]*centers[None,:]
    carriers=np.cos(phase)
    modulation=.35*np.sin(2*np.pi*1.25*t)
    colour=np.linspace(-1,1,len(centers));colour/=np.sqrt(np.mean(colour**2))
    controls=[];tol=plan['tolerances']

    def observe(name,mono,**extra):
        audio=np.column_stack((mono,.63*mono)) if mono.ndim==1 else mono
        starts,power=band_power(audio,plan)
        row,data=decompose(power,0,plan['hop']/rate,plan['slow_band_hz'],plan['minimum_power'])
        direct=scalar_power_check(audio,starts,power,plan)
        assert direct<tol['direct_dft_relative'],(name,direct)
        assert row['decomposition_relative_error']<tol['decomposition_relative']
        assert row['slow_decomposition_relative_error']<tol['decomposition_relative']
        assert row['parseval_relative_error']<tol['parseval_relative']
        save(name,starts,power,data)
        record=dict(name=name,summary=row,direct_dft_relative_error=direct,**extra)
        controls.append(record)
        return row,data,record

    row,_,_=observe('stationary_tones',carriers.sum(axis=1))
    assert max(row['all_rms_db_LR'])<tol['stationary_carrier_rms_db_maximum']

    row,data,record=observe('known_common_gain',carriers.sum(axis=1)*np.exp(modulation))
    assert min(row['common_variance_fraction_LR'])>tol['common_AM_fraction_minimum']
    centers_time=(np.arange(len(data['common']))*plan['hop']+(plan['size']-1)/2)/rate
    expected=.35*np.sin(2*np.pi*1.25*centers_time);expected-=expected.mean()
    error=float(DB*np.sqrt(np.mean((data['common'][:,0]-expected)**2)))
    record['known_envelope_rms_error_db']=error
    assert error<tol['known_envelope_rms_error_db'],error

    row,data,record=observe('known_spectral_colour',np.sum(carriers*np.exp(modulation[:,None]*colour),axis=1))
    assert max(row['common_variance_fraction_LR'])<tol['spectral_colour_common_fraction_maximum']
    expected=expected[:,None]*colour
    error=float(DB*np.sqrt(np.mean((data['shape'][:,:,0]-expected)**2)))
    record['known_envelope_rms_error_db']=error
    assert error<tol['known_envelope_rms_error_db'],error

    # A mixed analytic path additionally verifies the orthogonal energy budget.
    row,data,record=observe('known_gain_plus_colour',np.sum(carriers*np.exp(modulation[:,None]*(1+colour)),axis=1))
    assert abs(row['common_variance_fraction_LR'][0]-.5)<.002

    for seed in plan['control_seeds']:
        audio=np.random.default_rng(seed).normal(0,.1,(len(t),2))
        row,data,record=observe('stationary_gaussian_'+str(seed),audio,seed=seed,
            interpretation='Known stationary input; finite-window envelope motion is not extra source AM')
        # Decomposition must ignore a constant recording gain and stereo offset.
        starts,power=band_power(audio*.25,plan)
        _,changed=decompose(power,0,plan['hop']/rate,plan['slow_band_hz'],plan['minimum_power'])
        error=float(np.max(abs(changed['motion']-data['motion'])))
        assert error<tol['gain_invariance_absolute'],error
        record['constant_gain_invariance_error']=error

    # Fixed harmonic amplitudes, changing only the common pitch clock.
    root=43+7*t
    cycles=43*t+3.5*t*t
    mono=np.zeros(len(t))
    for harmonic in range(1,161):
        mono+=np.cos(2*np.pi*harmonic*cycles+.137*harmonic**2)/harmonic**.65
    observe('constant_amplitude_harmonic_pitch_sweep',mono,
        root_hz=[float(root[0]),float(root[-1])],
        interpretation='Fixed per-harmonic amplitudes, changing band occupancy/phase; not imposed AM')
    return controls
