"""Known-first physical22k sampling qualification, no recordings or fitting."""
import argparse
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
    from c1_source_prepare_v1.source import sample
    from locked_source_tail_v1.known import evaluate
    repo = Path(__file__).resolve().parents[1]; a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', cases=[], inputs={}, sources={}, material_read=False)
    try:
        parent = a.workspace/'references/analysis/c1_source_adapter_v1'
        known, audit = load(parent/'known1/report.json'), load(parent/'known_audit1/report.json')
        assert audit['verification_passed'] and audit['all_qualified']
        assert audit['producer_sha256'] == sha(parent/'known1/report.json')
        for path in (parent/'known1/report.json', parent/'known_audit1/report.json'): r['inputs'][str(path)] = sha(path)
        names = set(known['sources']) | {'tools/run_c1_sampling_known_v1.py', 'tools/audit_c1_sampling_known_v1.py',
            'tools/locked_source_tail_v1/kernel.py', 'tools/locked_source_tail_v1/known.py',
            'tools/locked_source_tail_v1/audit_kernel.py', 'research/c1_source_preparation_v1_plan.json'}
        names.update(path.relative_to(repo).as_posix() for path in (repo/'tools/c1_source_prepare_v1').glob('*.py'))
        for name in sorted(names):
            if name in known['sources']: assert sha(repo/name) == known['sources'][name]
            dest = a.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); r['sources'][name] = sha(dest)
        for row in known['cases']:
            path = parent/'known1'/row['file']; assert sha(path) == row['capture_sha256']; r['inputs'][str(path)] = sha(path)
            with np.load(path) as d: positions = d['source_coordinates']
            freq = np.array([64., 3200., 14080., 19072., 21952., 23424.])
            coef = np.array([[.13/(i+1)*np.exp(.29j*i), .0793/(i+1)*np.exp(1j*(1.1+.81*i))] for i in range(6)])
            label = row['label']
            if label == 'nonlinear_delay': coef[:, 1] = .63*coef[:, 0]*np.exp(-2j*np.pi*freq*.00035)
            if label == 'nonlinear_silent_right': coef[:, 1] = 0
            if label == 'nonlinear_zero': coef[:] = 0
            native = evaluate(np.arange(38400, dtype=np.longdouble)/48000, freq, coef)
            z = sample(native, 160., positions)
            truth = evaluate(np.asarray(positions, np.longdouble)-160, freq, coef, z['taps'])
            scale = float(np.sum(abs(coef))); error = float(np.max(abs(z['audio']-truth)))
            error = error/scale if scale else error; assert error <= 2e-10
            if label in ('nonlinear_zero', 'nonlinear_silent_right'): assert not np.count_nonzero(z['audio'][:, 1])
            output = a.out/(label+'.npz')
            np.savez_compressed(output, **z, native=native, positions=positions, frequencies=freq,
                coefficients=coef, truth=truth, source_start=np.array(160.))
            r['cases'].append(dict(label=label, file=output.name, sha256=sha(output),
                analytic_error_relative_source_L1=error, gate=2e-10))
            save(a.out/'report.json', r); print('C1_SAMPLING_KNOWN', label, error, flush=True)
        rejected = []
        native = np.zeros((38400, 2)); q = np.linspace(160.25, 160.45, 8193)
        for label, audio, positions, start in (
            ('left_support', native, q-.2, 160.), ('right_support', native, q+.3, 160.),
            ('nonfinite_audio', native*np.nan, q, 160.), ('complex_audio', native.astype(complex), q, 160.),
            ('reversed_queries', native, q[::-1], 160.), ('nonfinite_queries', native, q*np.nan, 160.),
            ('empty_queries', native, q[:0], 160.), ('nonfinite_start', native, q, np.nan)):
            try: sample(audio, start, positions)
            except ValueError: rejected.append(label)
            else: raise AssertionError(label)
        r.update(result='c1_sampling_known_measured', all_qualified=True, invalid_rejections=rejected,
            no_inverse_fit_or_runtime_change=True)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
