"""Fixed-plan local acoustic diagnostics using existing analysis kernels."""
import numpy as np
import soundfile as sf
from state_colour_v2.clock import follow
from state_dna_v1.compare import describe, difference
from phase_clock_v1.projection import polish


def qualify(audio, source_start, observed, case, plan, out):
    """No retries, parameter search, reference replacement or model export.

    A local pass would still not promote the failed generic phase method.
    Harmonic colour differences below use the common46.875Hz coordinate,
    not absolute source-frequency or isolated-component powers.
    """
    result = dict(case=case, references={}, comparisons=[])
    values = {}
    for reference in [plan['primary_reference'], *plan['comparison_references']]:
        item = dict(reference=reference)
        path = follow(observed['hz'], observed['seconds'], observed['power_low'],
                      *case['seconds'], case['initial_root_hz'], reference)
        item['tracking'] = path
        if not path['rows']:
            item['status'] = 'missing_coarse_path'
            result['references'][str(reference)] = item
            continue
        times = np.array([v['seconds'] for v in path['rows']])
        roots = np.array([v['root_hz'] for v in path['rows']])
        try:
            normalized, positions, evidence, z = describe(audio, source_start, times, roots,
                max(case['seconds'][0], float(times[0])), min(case['seconds'][1], float(times[-1])),
                reference=reference, phase_refiner=polish)
        except ValueError as exc:
            item.update(status='phase_rejected', reason=str(exc))
            result['references'][str(reference)] = item
            continue
        item.update(status='observed', evidence=evidence)
        values[reference] = evidence
        sf.write(out/f'reference{reference}_normalized.wav', normalized, 48000, subtype='FLOAT')
        np.savez_compressed(out/f'reference{reference}_coordinates.npz', source_seconds=positions, complex_rows=z)
        result['references'][str(reference)] = item
    primary = plan['primary_reference']
    if primary in values:
        evidence = values[primary]
        main_t = np.array(evidence['window_source_seconds'])
        main_r = np.array(evidence['window_root_hz'])
        for reference in plan['comparison_references']:
            if reference not in values:
                continue
            other = values[reference]
            other_t = np.array(other['window_source_seconds'])
            other_r = np.array(other['window_root_hz'])
            keep = (main_t >= other_t[0]) & (main_t <= other_t[-1])
            if not keep.any():
                result['comparisons'].append(dict(reference=reference, status='no_common_centres'))
                continue
            error = abs(main_r[keep]-np.interp(main_t[keep], other_t, other_r))/main_r[keep]
            delta = difference(evidence['harmonic_mean_power_LR'], other['harmonic_mean_power_LR'])
            result['comparisons'].append(dict(reference=reference, status='compared',
                common_centres=int(keep.sum()), relative_root_p95=float(np.percentile(error,95)),
                relative_root_max=float(error.max()), difference=delta,
                maximum_400_8000_shape_db=float(abs(np.array(delta['shape_after_scalar_removal_db_LR'])[2:5]).max())))
        gate = plan['diagnostic_gates']
        passing = [v for v in result['comparisons'] if v['status'] == 'compared' and
            v['relative_root_p95'] <= gate['maximum_root_relative_p95'] and
            v['maximum_400_8000_shape_db'] <= gate['maximum_shape_difference_db']]
        result['local_diagnostic_gate'] = bool(
            evidence['correction']['independent_agreement']['passed'] and
            evidence['nonoverlapping_four_cycle_window_upper_bound'] >= gate['minimum_nonoverlapping_four_cycle_windows'] and
            len(passing) >= gate['minimum_comparison_references'])
    else:
        result['local_diagnostic_gate'] = False
    result['generic_phase_qualification'] = 'not_passed_unchanged'
    result['model_export_allowed_by_this_report'] = False
    return result
