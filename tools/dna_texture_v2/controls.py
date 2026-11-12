"""Known comb/detuning/noise and independent direct sums; not real-engine labels."""
import numpy as np
from .observe import observe,analytic_band,repeat

def run(plan):
    count=58424;t=np.arange(count)/plan['sample_rate'];root=plan['sample_rate']/plan['acoustic_cycle_frames']
    def comb(ratio):
        out=np.zeros(count)
        for h in range(20,195):out+=np.cos(2*np.pi*(h*root*ratio)*t+.17*h)/np.sqrt(175)
        return np.column_stack((out,.8*out))
    rng=np.random.default_rng(77831);noise=rng.normal(size=(count,2))
    inputs=[('known_comb',comb(1)),('known_detuned_comb',comb(1.001)),('known_band_noise',noise)]
    rows={name:observe(x,plan) for name,x in inputs}
    pure=min(v['maximum_repeat'] for name in ('known_comb','known_detuned_comb') for band in rows[name] for v in band['repeat'])
    diffuse=max(v['maximum_repeat'] for band in rows['known_band_noise'] for v in band['repeat'])
    # The envelope is analytically known and periodic; reuse a broadband carrier
    # with many samples instead of an exact coefficient/timing oracle.
    amp=np.sqrt(1+.65*np.cos(2*np.pi*t*root)+.2*np.sin(4*np.pi*t*root))
    am=observe(noise*amp[:,None],plan)
    improvements=[v['heldout_improvement'] for b in am for v in b['periodic_envelope']]
    # Noise variance can limit this finite-block control. Use direct AM of a
    # high pure carrier for the fixed numerical envelope-recovery gate.
    carrier=np.cos(2*np.pi*4500*t)*amp
    known=observe(np.column_stack((carrier,carrier)),plan)[2]
    known_min=min(v['heldout_improvement'] for v in known['periodic_envelope'])
    x=inputs[1][1];a=repeat(analytic_band(x,plan['bands_hz'][-1],plan),plan)[0]
    b=repeat(analytic_band(x*.31,plan['bands_hz'][-1],plan),plan)[0]
    invariant=max(abs(u['maximum_repeat']-v['maximum_repeat']) for u,v in zip(a,b))
    errors=[b['direct_correlation_relative_error'] for r in rows.values() for b in r]
    limits=plan['controls']
    assert pure>=limits['comb_minimum_repeat'],pure
    assert diffuse<=limits['band_noise_maximum_repeat'],diffuse
    assert max(errors)<limits['direct_correlation_error'],max(errors)
    assert invariant<limits['gain_invariance_error'],invariant
    assert known_min>=limits['heldout_AM_minimum_improvement'],known_min
    return dict(result='pass',known_comb_minimum_repeat=pure,known_noise_maximum_repeat=diffuse,
                direct_correlation_relative_error=max(errors),gain_invariance_error=invariant,
                known_periodic_AM_minimum_heldout_improvement=known_min,
                known_noise_AM_heldout_improvement_range=[min(improvements),max(improvements)],
                observations=rows,known_periodic_noise_AM=am)
