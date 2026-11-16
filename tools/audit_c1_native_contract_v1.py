"""Exercise C1 adapter rejection boundaries using copies of a saved known case."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('workspace', 'out'):
        p.add_argument('--'+key, type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_native_diagnostics_v1.input import terminal
    source = a.workspace/'references/analysis/c1_source_adapter_v1/known1/affine_unequal'
    proof = a.workspace/'references/analysis/c1_registered_source_v1/known1'
    a.out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    original = {str(path):sha(path) for path in (source/'report.json', source/'capture.npz', proof/'report.json')}
    with np.load(source/'capture.npz', allow_pickle=False) as f:
        saved = {k:f[k] for k in f.files}
    info, audit = load(source/'report.json'), load(proof/'report.json')
    r = dict(result='running', original_inputs=original, rejections=[],
        sources={name:sha(repo/name) for name in ('tools/audit_c1_native_contract_v1.py',
            'tools/c1_native_diagnostics_v1/input.py')}, no_fit_or_original_mutation=True)
    try:
        for label in ('valid', 'running', 'unverified', 'changed_bytes', 'old_cutoff', 'wrong_clock', 'wrong_OSC'):
            root = a.out/label
            case, dest = root/'affine_unequal', root/'proof'
            case.mkdir(parents=True)
            dest.mkdir()
            z = {k:v.copy() for k,v in saved.items()}
            report, copied_proof = dict(info), dict(audit)
            if label == 'running':
                report['result'] = 'running'
            elif label == 'unverified':
                copied_proof['verification_passed'] = False
            elif label == 'old_cutoff':
                z['source_nominal_cutoff_Hz'] = np.array(14000.)
            elif label == 'wrong_clock':
                z['clock_coefficients'][3, 0] += 1e-6
            elif label == 'wrong_OSC':
                z['fitted'] *= 1.01
            np.savez_compressed(case/'capture.npz', **z)
            report['capture_sha256'] = sha(case/'capture.npz')
            save(case/'report.json', report)
            copied_proof['inputs'] = dict(audit['inputs'])
            copied_proof['inputs'][str(case/'report.json')] = sha(case/'report.json')
            copied_proof['inputs'][str(case/'capture.npz')] = report['capture_sha256']
            if label == 'changed_bytes':
                with (case/'capture.npz').open('ab') as stream:
                    stream.write(b'changed')
            save(dest/'report.json', copied_proof)
            try:
                _, binding = terminal(case, dest, workspace=a.workspace, known=True)
            except ValueError as error:
                assert label != 'valid', (label, str(error))
                r['rejections'].append(dict(label=label, reason=str(error)))
            else:
                assert label == 'valid', label
                r['valid'] = binding
        assert len(r['rejections']) == 6
        assert original == {name:sha(name) for name in original}
        r.update(result='independent_c1_native_contract_boundaries_verified', verification_passed=True,
            original_before_after_exact=True, known_success=1, rejected=6,
            synthetic_copies_do_not_replace_original_mathematical_proof=True,
            no_real_capture_or_live_job_consumed=True)
        save(a.out/'report.json', r)
        print('C1_NATIVE_CONTRACT', 1, 6, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
