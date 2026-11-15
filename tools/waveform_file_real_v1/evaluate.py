"""Complete locked metric and separate original-target/whole-context fidelity."""
import numpy as np
from observer_representer_v1.primal import PenaltyPrimal
from observer_representer_v1.dual import representer_certificate
from observer_frequency_v1.optimality import bound
from observer_inverse_v1.fit import complex_array
from waveform_structured_v1.penalty import TemporalPenalty
from waveform_correction_v1.trace import original_frobenius


def evaluate(system,shared,audio,values,base_info,reference):
    synthesis,metric = system.synthesis,system.metric
    q = shared.interleave(values['q'])
    fitted = complex_array(q,system.nshape)*system.scale[None]
    wave = synthesis.synthesize(fitted)
    residual = system@q-system.rhs(audio)
    u = -residual[:system.ysize]
    gradient = float(np.linalg.norm(system.rmatvec(residual))/max(np.linalg.norm(system.rmatvec(system.rhs(audio))),1e-300))
    rc,pc = bound(system,audio,fitted),representer_certificate(system,audio,fitted,u)
    primal = PenaltyPrimal(system)
    z = TemporalPenalty(system.nshape,system.D.toarray(),system.alpha,system.beta).root_transpose(q)
    rhs = np.r_[system.rhs(audio)[:system.ysize],np.zeros(system.nsize)]
    model = np.r_[system.rhs(values['wave_model_residual'])[:system.ysize],z]
    normal = primal.rmatvec(model)
    trace = original_frobenius(synthesis.positions,synthesis.orders,system.scale,metric,shared.prior.L,2)
    normA = trace['root_Frobenius']
    stable = float(np.linalg.norm(normal)/max(normA*np.linalg.norm(model),1e-300))
    backward = float(np.linalg.norm(primal@z-rhs-model)/max(np.linalg.norm(rhs),1e-300))
    error = wave-audio
    rows,ref = metric.forward(error),metric.forward(audio)
    target_error,target = error[2048:-2048],audio[2048:-2048]
    target_rows,target_ref = reference.forward(target_error),reference.forward(target)
    def ratio(x,y):
        den = float(np.linalg.norm(y))
        return float(np.linalg.norm(x)/den) if den else (0. if not np.count_nonzero(x) else None)
    metrics = dict(whole_wave_NRMSE=ratio(error,audio),target_wave_NRMSE=ratio(target_error,target),
        target_supported_band_complex_NRMSE=[ratio(target_rows[:,reference.bands==b],target_ref[:,reference.bands==b]) for b in range(6)],
        whole_supported_band_complex_NRMSE=[ratio(rows[:,metric.bands==b],ref[:,metric.bands==b]) for b in range(6)],
        whole_wave_regions_NRMSE=[ratio(error[s],audio[s]) for s in (slice(0,2048),slice(2048,-2048),slice(-2048,None))])
    fidelity = (metrics['target_wave_NRMSE'] is not None and metrics['target_wave_NRMSE']<.02
        and all(x is not None and x<.02 for x in metrics['target_supported_band_complex_NRMSE']))
    qualified = bool(gradient<2e-7 and stable<=1e-11 and backward<=1e-11
        and base_info['stable_root_guard_passed'] and rc['additional_gap_gate_passed'] and pc['additional_gap_gate_passed'])
    return dict(fitted=fitted,wave=wave,u=u,weights=metric.weights,band_power=metric.band_power,
        floor_active=metric.floor_active,original_model_residual=model,original_model_normal=normal),dict(
        production_original_trace=trace,original_gradient=gradient,original_stable_complete_normal=stable,
        original_backward_discrepancy=backward,residual_certificate=rc,representer_certificate=pc,
        metrics=metrics,solver_qualified=qualified,fidelity_qualified=bool(fidelity),
        target_rows_are_original_locked_metric=True,undefined_reference_ratios_not_converted_to_good_scores=True)
