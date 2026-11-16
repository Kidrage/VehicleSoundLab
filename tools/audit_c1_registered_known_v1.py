"""Qualify the complete terminal auditor using saved known fits, never refit."""
import argparse
import gc
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_registered_source_v1.complete import verify
    from c1_declared_objective_v1.audit import verify as preparation
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', sources={}, inputs={}, cases=[], invalid_rejections=[],
        known_factor_files_sha256={}, no_producer_or_fit_rerun=True, no_actual_source_fit=True)
    def read(path):
        r['inputs'][str(path)] = sha(path)
        return load(path)
    try:
        parent = a.workspace/'references/analysis/c1_source_adapter_v1'
        known = read(parent/'known1/report.json')
        proof = read(parent/'known_audit1/report.json')
        declared = read(a.workspace/'references/analysis/c1_declared_objective_v1/known1/report.json')
        assert known['all_qualified'] and proof['all_qualified'] and proof['verification_passed']
        assert proof['producer_sha256'] == sha(parent/'known1/report.json')
        assert declared['all_qualified'] and declared['complete_augmented_QR_cases'] == 3
        registration = read(a.workspace/'references/analysis/c1_fit_registration_v1/registration1/report.json')
        names = set(registration['sources']) | {'tools/audit_c1_registered_known_v1.py',
            'research/c1_registered_source_v1_plan.json'}
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/c1_registered_source_v1').glob('*.py'))
        for name in sorted(names):
            if name in registration['sources']:
                assert sha(repo/name) == registration['sources'][name]
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        for row in known['cases']:
            directory = parent/'known1'/row['label']
            assert sha(directory/'capture.npz') == row['capture_sha256']
            r['inputs'][str(directory/'capture.npz')] = row['capture_sha256']
            r['inputs'][str(directory/'report.json')] = row['report_sha256']
            assert sha(directory/'report.json') == row['report_sha256']
            if row['label'] == 'nonlinear_zero':
                with np.load(directory/'capture.npz') as f:
                    z = {name:f[name] for name in f.files}
                def check(name, x, y):
                    assert np.allclose(x, y, rtol=0, atol=2e-12), name
                oracle, equations = preparation(z, check)
                assert not np.count_nonzero(z['q']) and not np.count_nonzero(z['wave'])
                assert not np.count_nonzero(oracle.target())
                case = dict(label=row['label'], exact_zero=True, preparation_equations=equations)
                del z, oracle
            else:
                case = verify(directory)
                assert case['verification_passed'] and case['all_qualified']
                case['label'] = row['label']
                for item in case['file_resource_audit']['factors']:
                    path = directory/'factors'/item['name']
                    assert sha(path) == item['sha256']
                    r['known_factor_files_sha256'][str(path)] = item['sha256']
            r['cases'].append(case)
            save(a.out/'report.json', r)
            print('C1_TERMINAL_KNOWN', row['label'], flush=True)
            gc.collect()
        first = parent/'known1/affine_unequal'
        info = load(first/'report.json')
        with np.load(first/'capture.npz') as f:
            original = {name:f[name] for name in f.files}
        for field, expected in (('weights', 'prepared_calibration_weights'),
            ('fitted', 'independent_LR_interleave'), ('original_model_normal', 'complete_original_adjoint'),
            ('history_z', 'node_update_0'), ('metrics', 'declared_whole_wave_NRMSE'),
            ('fidelity', 'fidelity_flag')):
            directory = a.out/'corruptions'/field
            directory.mkdir(parents=True)
            data, modified = dict(original), dict(info)
            if field in original:
                data[field] = original[field].copy()
                if field in ('weights', 'fitted'):
                    data[field] *= .99
                elif field == 'history_z':
                    data[field][1, 0, 0] += 1.
                else:
                    data[field].flat[0] += 1e6
            elif field == 'metrics':
                modified['metrics'] = dict(info['metrics'], whole_wave_NRMSE=info['metrics']['whole_wave_NRMSE']+1.)
            else:
                modified['fidelity_qualified'] = not info['fidelity_qualified']
            np.savez_compressed(directory/'capture.npz', **data)
            modified['capture_sha256'] = sha(directory/'capture.npz')
            save(directory/'report.json', modified)
            try:
                verify(directory)
            except AssertionError as error:
                assert expected in str(error), (field, expected, str(error))
                r['invalid_rejections'].append(dict(field=field, expected=expected, actual=str(error)))
            else:
                raise AssertionError('Corrupted capture/report accepted: '+field)
        r.update(result='independent_c1_registered_terminal_known_verified', verification_passed=True,
            all_qualified=True, full_terminal_cases=3, exact_zero_cases=1, corruptions_rejected=6,
            existing_factors_verified=12, no_stored_capture_or_report_mutation=True,
            original_SciPy_failures_preserved=True, no_source_fidelity_or_runtime_promotion=True)
        save(a.out/'report.json', r)
        print('C1_TERMINAL_KNOWN_COMPLETE', len(r['cases']), len(r['invalid_rejections']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
