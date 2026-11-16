"""Preserve declared metric, full LR joint moments and tone-clock correspondence."""
import numpy as np
from locked_source_error_v1.assessment import virtual_split,locked_rows
from .clock import bounds


def analyze(z,certificate):
    amplitude=float(z['amplitude']);weights=z['weights'];target=z['target'];fit=z['wave'][2048:-2048]
    arrays,summary=virtual_split(target,fit,weights,amplitude,z['orders'])
    reference,_,_,starts=locked_rows(target,weights,amplitude)
    error,_,_,_=locked_rows(fit-target,weights,amplitude)
    full,_,_,whole_starts=locked_rows(z['wave']-z['audio'],weights,amplitude)
    ids=np.searchsorted(whole_starts,starts+2048)
    if not np.array_equal(full[ids],error):raise ValueError('Target observer is not an exact whole-context restriction')
    joint=np.concatenate((reference,error),axis=2)
    gram=np.einsum('wki,wkj->kij',joint,joint.conj(),optimize=True)
    frequency=arrays['virtual_frequency']
    derivative_bounds=np.array([bounds(z['clock_x'],z['clock_coefficients'],float(s+2048),float(s+2048+4095)) for s in starts])
    mapping=frequency[None,:,None]/(65536*derivative_bounds[:,None,::-1])
    high=frequency>=14000
    den=float(np.linalg.norm(reference[:,high]));num=float(np.linalg.norm(error[:,high]))
    gap=float(certificate['gap_upper_bound'])
    if not np.isfinite(gap) or gap<0:raise ValueError('Finite nonnegative inherited optimality gap required')
    maximum_delta=float(np.sqrt(gap)/den)
    arrays.update(virtual_joint_reference_error_Gram=gram,clock_derivative_bounds=derivative_bounds,
        constant_coordinate_tone_physical_Hz_envelopes=mapping,target_rows_in_whole_context=ids,
        target_reference_rows=reference,target_error_rows=error)
    summary.update(nominal_original_optimality=dict(
        highest_band_reference_norm=den,highest_band_residual_norm=num,
        inherited_gap_upper_bound=gap,inherited_weighted_distance_bound=float(np.sqrt(gap)),
        maximum_possible_highest_NRMSE_change=maximum_delta,
        exact_same_objective_optimum_NRMSE_lower_bound=float(max(0.,num-np.sqrt(gap))/den),
        original_highest_NRMSE=num/den,original_fidelity_gate=.02,
        exact_target_observer_restriction_verified=True,
        inherited_certificate_is_floating_point_not_interval_arithmetic=True),
        source_clock_derivative_seconds_per_coordinate_sample_range=[float(derivative_bounds[:,0].min()),float(derivative_bounds[:,1].max())],
        highest_centre_single_tone_physical_Hz_range=[float(mapping[:,1152,0].min()),float(mapping[:,1152,1].max())],
        frequency_mapping_is_single_tone_coordinate_correspondence_not_Fourier_power_attribution=True,
        no_support_vs_regularization_or_mechanical_or_audible_cause_identified=True)
    return arrays,summary
