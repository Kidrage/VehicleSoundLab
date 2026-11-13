"""Known amplitude laws, mapping failures, and a non-engine scale counterexample."""
import numpy as np
from .model import compile_model,predict
from accel_ridges_v1.observe import associate
from accel_material_v1.features import whiten,scale_match
from accel_material_v1.checks import controls as scale_controls
from idle_material_v1.features import spectrum


def controls(scale_plan,ridge_plan):
    x=np.linspace(0,.16,9);slope=np.array([2.7,-1.3]);a=np.array([.08,.05])*np.exp(x[:,None]*slope)
    model=compile_model(x,a,500*np.exp(x),np.exp(x),np.log(1.03));assert model is not None
    error=float(abs(np.array(model['slope_LR'])-slope).max());assert error<1e-12
    q=.11;truth=np.array([.08,.05])*np.exp(q*slope);pred=predict(model,q)
    assert abs(pred['log_linear']-truth).max()<1e-14
    constant=compile_model(x,np.tile([.08,.05],(len(x),1)),500*np.exp(x),np.exp(x),np.log(1.03))
    assert max(abs(np.array(constant['slope_LR'])))<1e-12
    # Prediction consumes no target amplitude; report both changed-law errors.
    first=predict(model,q)['log_linear'];changed_truth=truth*np.array([3.,.2])
    second=predict(model,q)['log_linear'];assert np.array_equal(first,second)
    changed_error=20*np.log10(changed_truth/second);assert max(abs(changed_error))>3
    assert compile_model(x[:2],a[:2],500*np.exp(x[:2]),np.exp(x[:2]),np.log(1.03)) is None
    refs=np.arange(5,31)*60.613;ratio=2**(-3/192)
    measured=refs*ratio+.7*np.sin(np.arange(len(refs)))
    base=associate(refs,measured,ratio,4.,ridge_plan);assert base['state']==['unique']*26
    missing=associate(refs,np.delete(measured,8),ratio,4.,ridge_plan);assert missing['state'][8]=='absent'
    neighbour=associate(refs,np.sort(np.r_[measured,measured[8]+4.]),ratio,4.,ridge_plan)
    assert neighbour['state'][8]=='ambiguous'
    noise=np.random.default_rng(548117).normal(0,.1,(12000,2));power=spectrum(noise,scale_plan['bands_hz'])
    feature=whiten(power['cells'],power['frequency'],scale_plan['spectral_scale'])
    self_match=scale_match(feature,feature,scale_plan['spectral_scale']);assert self_match['supported']
    return dict(powerlaw_slope_error=error,powerlaw_amplitude_error=float(abs(pred['log_linear']-truth).max()),
        constant_law_exact=True,training_independent_of_target=True,changed_law_error_db_LR=changed_error.tolist(),
        same_coordinate_does_not_determine_target_law=True,dense26_unique=True,removed_absent=True,neighbour_ambiguous=True,
        scale_controls=scale_controls(scale_plan),identical_noise_self_match=self_match,
        warning='Same-spectrum noise passes self scale match; no engine-source or mechanical-order identity')
