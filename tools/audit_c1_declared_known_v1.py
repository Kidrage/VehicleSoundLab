"""Full known equations and complete dense QR before declared real input audit."""
import argparse
import gc
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_declared_objective_v1.audit import verify
    from c1_declared_objective_v1.dense import matrix, solve
    repo = Path(__file__).resolve().parents[1]; a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], sources={}, inputs={}, material_read=False,
        measurement_identity='vsl.c1-declared-objective/1', no_producer_solver_or_adapter_imports=True)
    def bind(path):
        path = Path(path); r['inputs'][str(path)] = sha(path); return path
    def checker(errors):
        def check(name, actual, expected, gate=2e-12):
            actual, expected = np.asarray(actual), np.asarray(expected)
            assert actual.shape == expected.shape and np.isfinite(actual).all() and np.isfinite(expected).all(), name
            scale = max(1., float(np.max(abs(expected))) if expected.size else 0.)
            error = float(np.max(abs(actual-expected)))/scale if actual.size else 0.
            assert error <= gate, (name, error, gate)
            errors[name] = error
        return check
    try:
        parent = a.workspace/'references/analysis/c1_source_adapter_v1'
        known = load(bind(parent/'known1/report.json')); proof = load(bind(parent/'known_audit1/report.json'))
        assert known['result'] == 'c1_source_known_measured' and known['all_qualified']
        assert proof['result'] == 'independent_c1_source_known_verified' and proof['verification_passed'] and proof['all_qualified']
        assert proof['producer_sha256'] == sha(parent/'known1/report.json')
        for path, expected in proof['inputs'].items(): assert sha(path) == expected; r['inputs'][path] = expected
        names = set(known['sources']) | {'tools/audit_c1_declared_known_v1.py', 'tools/audit_c1_declared_real_v1.py',
            'research/c1_declared_objective_v1_plan.json', 'tools/locked_source_guard_v1/measurement.py',
            'tools/observer_supported_v1/full_oracle.py', 'tools/waveform_file_real_v1/audit_oracle.py'}
        names.update(path.relative_to(repo).as_posix() for path in (repo/'tools/c1_declared_objective_v1').glob('*.py'))
        for name in sorted(names):
            if name in known['sources']: assert sha(repo/name) == known['sources'][name]
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        for row in known['cases']:
            path = bind(parent/'known1'/row['file']); assert sha(path) == row['capture_sha256']
            with np.load(path) as f: z = {k:f[k] for k in f.files}
            errors = {}; check = checker(errors)
            oracle, equations = verify(z, check)
            assert equations['original_SciPy_reference_RHS_gate_passed']
            difference = None
            if row['label'] != 'nonlinear_zero':
                B, tail, target = matrix(oracle)
                q = z['probe_q'].reshape(-1, 2); y = z['probe_rows'].reshape(-1, 2)
                size = len(B)
                check('complete_dense_forward', np.vstack((B@q, tail@q)), oracle.forward(z['probe_q']).reshape(-1, 2), gate=2e-8)
                check('complete_dense_adjoint', B.T@y[:size]+tail.T@y[size:], oracle.backward(z['probe_rows']).reshape(-1, 2), gate=2e-8)
                check('complete_dense_normal', B.T@(B@q)+tail.T@(tail@q), oracle.backward(oracle.forward(z['probe_q'])).reshape(-1, 2), gate=2e-8)
                direct = solve(B, tail, target)
                difference = float(np.linalg.norm(z['q']-direct)/np.linalg.norm(direct)); assert difference < 2e-7
                if row['label'] == 'nonlinear_silent_right': assert not np.count_nonzero(direct[:, 1])
                del B, tail, target, direct
            else:
                assert not np.count_nonzero(oracle.target()) and not np.count_nonzero(z['q']) and not np.count_nonzero(z['wave'])
                assert equations['declared_RHS_max_absolute'] == 0.
            r['cases'].append(dict(label=row['label'], complete_equations=equations,
                independent_complete_QR_relative_coefficient_difference=difference,
                maximum_errors=errors, verified=True))
            save(a.out/'report.json', r); print('C1_DECLARED_KNOWN', row['label'], difference, max(errors.values()), flush=True)
            del z, oracle; gc.collect()
        first = known['cases'][0]
        with np.load(parent/'known1'/first['file']) as f: original = {k:f[k] for k in f.files}
        rejected = []
        for field, reason in (('weights', 'calibration_weights'), ('band_power', 'calibration_band_power'),
            ('sigma', 'calibration_sigma'), ('probe_rhs', 'full_RHS'), ('probe_forward', 'full_forward'),
            ('probe_adjoint', 'full_adjoint'), ('probe_normal', 'full_normal'), ('target_slots', 'target_slots'),
            ('target', 'new_target_slice'), ('metric_target', 'legacy_metric_target')):
            bad = dict(original); bad[field] = original[field].copy()
            if field in ('weights', 'sigma', 'target', 'metric_target'): bad[field] *= .99
            elif field == 'target_slots': bad[field] += 1
            elif field == 'band_power': bad[field] += .01
            else: bad[field].flat[0] += 1.
            try: verify(bad, checker({}))
            except AssertionError as error:
                assert reason in str(error), (field, reason, str(error))
                rejected.append(dict(field=field, reason=reason))
            else: raise AssertionError('Corrupted packet accepted: '+field)
        r.update(result='independent_c1_declared_known_verified', verification_passed=True,
            all_qualified=True, complete_augmented_QR_cases=3, invalid_rejections=rejected,
            no_fitting_or_packet_mutation=True, original_reference_audits_unchanged=True)
        save(a.out/'report.json', r); print('C1_DECLARED_KNOWN_COMPLETE', len(rejected), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
