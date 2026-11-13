"""Independent scalar complex phase products on the entire declared torus grid."""
import argparse
import cmath
import math
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'bound', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load, save, sha


def oracle(c, expected):
    # Explicit scalar complex coordinates avoid the producer's exponent matrix.
    coef = np.asarray(c)
    minima = np.full(4, np.inf)
    at_saved = np.empty(4)
    for i in range(32):
        for j in range(32):
            for k in range(32):
                z0, z1, z2 = [cmath.exp(2j*math.pi*v/32) for v in (i, j, k)]
                modes = [z0, z1, z2, z1*z0.conjugate(), z2*z0.conjugate(), z2*z1.conjugate()]
                for band in range(4):
                    value = math.fsum([coef[0, band]] + [coef[m+1, band]*z.real+coef[m+7, band]*z.imag
                                                       for m, z in enumerate(modes)])
                    minima[band] = min(minima[band], value)
                    if [i, j, k] == expected['grid_argmin_indices'][band]:
                        at_saved[band] = value
    error = max(float(abs(minima-expected['grid_minimum']).max()),
                float(abs(at_saved-expected['grid_minimum']).max()))
    assert error < 1e-12
    curvature = np.array([math.fsum(math.hypot(coef[m+1, b], coef[m+7, b])*(1 if m < 3 else 4)
                                    for m in range(6)) for b in range(4)])
    debt = curvature*math.pi**2/(2*32**2)
    lower = minima-debt-1e-10
    status = ['positive_bound' if lo > 0 else 'negative_counterexample' if hi < -1e-10 else 'UNKNOWN'
              for lo, hi in zip(lower, minima)]
    assert expected['grid_size'] == 32 and expected['points'] == 32768 and expected['numerical_guard'] == 1e-10
    assert abs(curvature-expected['curvature_bound']).max() < 1e-12
    assert abs(debt-expected['covering_debt']).max() < 1e-12
    assert abs(lower-expected['global_lower_bound']).max() < 1e-12
    assert status == expected['status']
    assert bool(all(s == 'positive_bound' for s in status)) == expected['all_bands_positive']
    return error


a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out/'executed_auditor.py')
r = dict(result='running', maximum_grid_error=0., known_models=0, source_control_models=0)
try:
    observed, bounds = load(a.input/'report.json'), load(a.bound/'report.json')
    assert bounds['result'] == 'dependent_phase_bounds_complete_no_sound_promotion'
    assert bounds['input_report_sha256'] == sha(a.input/'report.json')
    assert bounds['original_gate_unchanged'] == observed['future_synthesis_prerequisite']
    for name, digest in bounds['sources'].items():
        assert sha(a.bound/'exact_sources'/name) == digest
    for row in bounds['known']:
        error = oracle(row['coefficients'], row['result'])
        r['maximum_grid_error'] = max(r['maximum_grid_error'], error)
        exact = row['analytic_minimum']
        assert max(row['result']['global_lower_bound']) <= exact+1e-12
        assert exact <= min(row['result']['grid_minimum'])+1e-12
        expected = {'positive_dependent': 'positive_bound', 'negative': 'negative_counterexample',
                    'constant': 'positive_bound', 'zero_minimum': 'UNKNOWN'}[row['label']]
        assert row['result']['status'] == [expected]*4
        r['known_models'] += 1
    print(dict(stage='known', models=r['known_models']), flush=True)
    for row, source in zip(bounds['observations'], observed['observations']):
        assert row['group'] == source['group']
        error = oracle(source['models']['expanded']['coefficients'], row['certificate'])
        r['maximum_grid_error'] = max(r['maximum_grid_error'], error)
        r['source_control_models'] += 1
        print(dict(group=row['group'], verified=True), flush=True)
    assert r['known_models'] == 6 and r['source_control_models'] == 4
    assert bounds['observations'][0]['certificate']['status'][1] == 'negative_counterexample'
    r.update(result='all10_models_full32768point_bounds_independently_verified',
             input_report_sha256=sha(a.input/'report.json'), bound_report_sha256=sha(a.bound/'report.json'),
             original_gate_unchanged=True, source_2_to4k_negative_phase_counterexample_verified=True,
             audio_or_runtime_profile_exported=False, runtime_changed=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
print(r, flush=True)
