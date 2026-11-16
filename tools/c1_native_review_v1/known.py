"""Observable geometry and signed cancellation controls before real inputs."""
import copy
import numpy as np
from .measure import analyze
from .audit import verify


def qualify(check):
    n = np.arange(8192)
    angle = 2*np.pi*91*n/4096
    raw = np.column_stack((.3*np.cos(angle), .2*np.cos(angle+.4)))
    phase = np.column_stack((.3*np.cos(angle+.8), .2*np.cos(angle+1.2)))
    cases = dict(scaled=(raw, raw, raw, 1.7*raw),
        phase_shift=(raw, raw, raw, phase), zero_candidate=(raw, raw, raw, np.zeros_like(raw)),
        silent_right=tuple(np.column_stack((v[:, 0], np.zeros(len(v)))) for v in (raw, raw, raw, 1.3*raw)),
        signed_cancellation=(raw, 2*raw, raw, raw),
        silence=tuple(np.zeros_like(raw) for _ in range(4)))
    summaries = {}
    saved_case = None
    for label, values in cases.items():
        arrays, rows = analyze(*values)
        result = verify(arrays, rows, lambda name, a, b, scale:check(label+'_'+name, a, b, scale))
        ref = arrays['raw_bin_power'].sum()
        radial = arrays['bin_radial_error_power'].sum()
        angular = arrays['bin_angular_error_power'].sum()
        if label == 'scaled':
            check('scaled_known_radial', radial/ref, .7**2, 1.)
            check('scaled_known_angular', angular/ref, 0., 1.)
            saved_case = (arrays, rows)
        elif label == 'phase_shift':
            check('phase_known_radial', radial/ref, 0., 1.)
            check('phase_known_angular', angular/ref, 2*(1-np.cos(.8)), 1.)
        elif label == 'zero_candidate':
            check('zero_known_radial', radial/ref, 1., 1.)
            check('zero_known_angular', angular, 0., 1.)
        elif label == 'silent_right':
            assert np.count_nonzero(arrays['bin_error_power'][:, 1]) == 0
        elif label == 'signed_cancellation':
            assert arrays['bin_error_power'].sum() == 0
            g = arrays['bin_component_Gram'].sum(axis=0)
            check('known_negative_cross', 2*(g[0, 2]+g[1, 3]).real/ref, -2., 1.)
        summaries[label] = result
    # Both the spectral arrays and derived table must be checked, not trusted.
    rejected = []
    for label in ('spectrum', 'ratio', 'signed_cross'):
        arrays = {k:v.copy() for k,v in saved_case[0].items()}
        rows = copy.deepcopy(saved_case[1])
        if label == 'spectrum': arrays['bin_angular_error_power'][91, 0] += .01
        elif label == 'ratio': rows[0]['combined_complex_NRMSE'] += .1
        else: rows[0]['component_signed_cross_FS2_LR'][0][1][0] += .01
        def reject_check(name, a, b, scale):
            if np.max(abs(np.asarray(a)-np.asarray(b))) > 2e-11*max(scale, 1e-300):
                raise ValueError(name)
        try:
            verify(arrays, rows, reject_check)
        except (ValueError, AssertionError):
            rejected.append(label)
        else:
            raise AssertionError('Corruption was not rejected: '+label)
    return dict(cases=summaries, corruption_rejections=rejected,
        known_before_actual=True, refitted_or_launched_source=False)
