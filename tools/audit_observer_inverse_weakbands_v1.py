"""Per-mean-power audit; a strong band cannot hide a weak band's errors."""
import argparse, os, shutil, sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--study', type=Path, nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_inverse_v1.audit_oracle import observe, statistics
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    repo = Path(__file__).resolve().parents[1]
    for i, name in enumerate(('tools/observer_inverse_v1/audit_oracle.py',
                              'tools/circular_phase_lift_v1/audit_oracle.py')):
        shutil.copy2(repo/name, a.out/f'executed_oracle_{i}.py')
    r = dict(result='running', cases=[], studies={}, captures=0,
        normalization='Each channel mean power; covariance/lag by outer channel means; complex cross by sqrt(Lmean*Rmean). Fixed floor1e-24.',
        maximum_errors={}, gate=2e-9, no_new_waveform_synthesis=True)
    def record(name, x, y, denominator):
        error = float(np.max(abs(x-y)/denominator))
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))
        if error >= r['gate']:
            raise AssertionError((name, error))
        return error
    def check(measured, saved, prefix, pk, ck):
        truth = statistics(measured[pk], measured[ck])
        mean = truth['mean']
        channel = np.maximum(mean, 1e-24)
        cross = np.maximum(np.sqrt(mean[::2]*mean[1::2]), 1e-24)
        joint = np.maximum(mean[::2]+mean[1::2], 1e-24)
        covariance = np.maximum(mean[:,None]*mean[None,:], 1e-24)
        record('raw_'+pk, measured[pk], saved[pk], channel[None])
        record('raw_'+ck, measured[ck], saved[ck], cross[None])
        scales = dict(mean=channel, covariance=covariance, lag_covariance=covariance[None],
            CV=1., complex_coherence=1., mid_power=joint, side_power=joint)
        for field, denominator in scales.items():
            record(prefix+field, truth[field], saved[prefix+field], denominator)
        for field in ('power_defined', 'coherence_defined'):
            assert np.array_equal(truth[field], saved[prefix+field])
        if 'chunks_'+prefix+'mean' in saved:
            chunks = np.array_split(np.arange(len(measured[pk])), 3)
            for j, indices in enumerate(chunks):
                stats = statistics(measured[pk][indices], measured[ck][indices])
                for field in ('mean', 'CV', 'complex_coherence'):
                    denominator = np.maximum(stats['mean'], 1e-24) if field == 'mean' else 1.
                    record('chunks_'+prefix+field, stats[field], saved['chunks_'+prefix+field][j], denominator)
        return dict(channel_mean_power=mean.tolist(),
            weakest_to_strongest_mean_ratio=float(mean.min()/max(mean.max(), 1e-24)))
    try:
        # Known counterexamples: the former global scale would pass both,
        # while the mean-normalized check must detect two-percent errors.
        ref = np.array([1., 1e-9]);bad = ref.copy();bad[1] *= 1.02
        raw_global = float(abs(bad-ref).max()/ref.max())
        raw_local = float((abs(bad-ref)/ref).max())
        cov = np.outer(ref, ref);wrong = cov.copy();wrong[1,1] *= 1.02
        cov_global = float(abs(wrong-cov).max()/cov.max())
        cov_local = float((abs(wrong-cov)/np.maximum(np.outer(ref,ref),1e-24)).max())
        assert raw_global < r['gate'] and cov_global < r['gate']
        assert raw_local > .019 and cov_local > .019
        r['known_counterexamples'] = dict(raw_global=raw_global, raw_local=raw_local,
            covariance_global=cov_global, covariance_local=cov_local)
        save(a.out/'report.json', r)
        for study in a.study:
            producer = load(study/'report.json')
            assert producer['result'] == 'observer_inverse_all6_measured' and len(producer['cases']) == 6
            r['studies'][str(study)] = sha(study/'report.json')
            for case in producer['cases']:
                folder = study/case['label']
                captures = [('source.npz', case['source_sha256'])]
                captures += [(v['file'],v['sha256']) for v in case['variants'].values()]
                for name, digest in captures:
                    path = folder/name;assert sha(path) == digest
                    with np.load(path) as z:
                        measured = observe(z['audio'][:,None,:], case['root_hz'], producer['bands'])
                        record('coefficients_absolute', measured['coefficients'], z['coefficients'], 1.)
                        row = dict(study=study.name, label=case['label'], file=name, sha256=digest)
                        row['line'] = check(measured, z, 'line_', 'power', 'cross')
                        row['broad'] = check(measured, z, 'broad_', 'broadband_power', 'broadband_cross')
                    r['cases'].append(row);r['captures'] += 1
                print('AUDITED weak bands', study.name, case['label'], flush=True)
                save(a.out/'report.json', r)
        r.update(result='independent_observer_inverse_weakbands_passed',
            auditor_sha256=sha(__file__), all_raw_power_cross_and_per_mean_covariance_verified=True)
        assert r['captures'] == 18*len(a.study)
        save(a.out/'report.json', r);print(r['result'], r['captures'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error));save(a.out/'report.json', r);raise


if __name__ == '__main__':
    main()
