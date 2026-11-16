"""Separate reference-frame and calibration rounding without changing gates."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'study', 'failed-audit', 'out'): p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_fit_v1.oracle import make
    from locked_source_guard_v1.measurement import frame as declared
    from observer_complete_v1.audit_oracle import full_frame
    a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_diagnosis.py')
    r = dict(result='running', cases=[], inputs={}, no_fit_or_original_source_changes=True)
    def bind(path):
        path = Path(path); r['inputs'][str(path)] = sha(path); return path
    try:
        study = load(bind(a.study/'report.json')); failed = load(bind(a.failed_audit/'report.json'))
        assert study['result'] == 'c1_source_one_real_prepared' and failed['result'] == 'failed'
        assert failed['producer_sha256'] == sha(a.study/'report.json') and "'full_RHS'" in failed['error']
        root = a.workspace/'references/analysis/c1_source_adapter_v1'
        known = load(bind(root/'known1/report.json')); audit = load(bind(root/'known_audit1/report.json'))
        assert audit['verification_passed'] and audit['all_qualified'] and audit['producer_sha256'] == sha(root/'known1/report.json')
        cases = [(row['label'], root/'known1'/row['file'], True) for row in known['cases']]
        cases += [(row['label'], a.study/row['file'], False) for row in study['cases']]
        for label, path, is_known in cases:
            with np.load(bind(path)) as f: z = {k:f[k] for k in f.files}
            oracle, old = make(z['audio'], z['metric_target'], z['positions'], z['orders'], z['scale'])
            original = np.r_[oracle.target(), np.zeros(len(z['probe_rhs'])-oracle.data_size)]
            starts = np.arange(-3840, len(z['audio']), 256); keep = (starts>=0)&(starts+4096<=len(z['audio']))
            variants = {}
            for frame_name, frame in (('scipy_reference', full_frame), ('declared_FP64_order', declared)):
                rows, _ = frame(z['audio'])
                for calibration, weights, amplitude, sigma in (
                    ('independent_legacy', old['weights'], old['amplitude'], old['sigma']),
                    ('frozen_legacy', z['weights'], float(z['amplitude']), float(z['sigma']))):
                    spectral = rows[keep]*amplitude*weights[None, :, None]
                    rhs = np.r_[z['audio'].ravel()/sigma, spectral.real.ravel(), spectral.imag.ravel(),
                        np.zeros(len(z['probe_rhs'])-oracle.data_size)]
                    delta = rhs-z['probe_rhs']; norm = max(1., float(np.max(abs(rhs))))
                    variants[frame_name+'__'+calibration] = dict(maximum_absolute=float(np.max(abs(delta))),
                        normalized_by_maximum_expected=max(abs(delta))/norm,
                        original_2e_12_gate_passed=bool(np.max(abs(delta))/norm <= 2e-12))
            assert variants['declared_FP64_order__frozen_legacy']['maximum_absolute'] == 0.
            original_error = float(np.max(abs(original-z['probe_rhs']))/max(1., float(np.max(abs(original)))))
            assert abs(original_error-variants['scipy_reference__independent_legacy']['normalized_by_maximum_expected']) == 0.
            if is_known: assert original_error <= 2e-12
            else:
                assert original_error > 2e-12
                assert abs(original_error-2.5585096571438003e-12) < 1e-24
            r['cases'].append(dict(label=label, known=is_known, original_cross_operator_error=original_error,
                variants=variants, legacy_weights_maximum_relative_difference=float(np.max(abs(old['weights']-z['weights'])/z['weights']))))
            save(a.out/'report.json', r); print('C1_RHS_DIAGNOSIS', label, original_error, flush=True)
        r.update(result='c1_preparation_RHS_rounding_diagnosed', known_controls_before_real=True,
            original_failed_audit_retained=True, original_cross_operator_gate_passed=False,
            declared_frozen_RHS_bitwise_identical_all_five=True,
            complete_preparation_audit_not_repaired=True, certified_crossFFT_bound=False,
            next='Separate known-first complete declared-rounded objective audit with all equations and original gates; original SciPy-reference failure remains false; no fit launch')
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out/'report.json', r); raise


if __name__ == '__main__': main()
