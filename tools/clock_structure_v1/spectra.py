"""Reuse the qualified observer with an explicitly named analytic reference."""
from locked_source_tail_v1.measure import measure as established_measure


def measure(values, weights, amplitude, reference):
    if reference not in values or 'exact_registered' in values:
        raise ValueError('An explicit unambiguous diagnostic reference is required')
    renamed = {('exact_registered' if name == reference else name): value for name, value in values.items()}
    arrays, info = established_measure(renamed, weights, amplitude)
    arrays = {(reference+key[len('exact_registered'):] if key.startswith('exact_registered_') else key): value
              for key, value in arrays.items()}
    for key in ('signals', 'comparisons'):
        info[key][reference] = info[key].pop('exact_registered')
    info['diagnostic_reference'] = reference
    info['reference_is_declared_analytic_control_not_original_recorded_clock'] = True
    return arrays, info
