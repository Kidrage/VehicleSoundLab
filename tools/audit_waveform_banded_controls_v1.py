"""Independent scalar-DFT/band-root audit, including actual BLAS copy behavior.

The original control auditor does not inspect packed metric/root extras. This
additional gate checks every entry and every basis direction in those controls.
Dense expansion is restricted to these 41-sample source-independent fixtures.
"""
import argparse
import math
import os
import shutil
import sys
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'original-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from waveform_banded_v1.metric import BandedMetric
    from waveform_structured_v1.resources import ArrayLedger
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[], maximum_errors={}, input_sha256={})

    def consume(path):
        r['input_sha256'][str(path)] = sha(path)
        return path

    def check(name, actual, expected):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape, name
        error = float(np.max(abs(actual-expected))/max(1., abs(expected).max()))
        assert np.isfinite(error) and error < 2e-12, (name, error)
        r['maximum_errors'][name] = max(error, r['maximum_errors'].get(name, 0.))

    def unpack(bands, symmetric=False):
        size, frames = bands.shape
        dense = np.zeros((frames, frames))
        for j in range(frames):
            for d in range(min(size, frames-j)):
                dense[j+d, j] = bands[d, j]
                if symmetric:
                    dense[j, j+d] = bands[d, j]
        return dense

    def scalar_metric(z):
        frames, size = len(z['W']), len(z['window'])
        rows = []
        for start in z['starts']:
            for k in range(size//2+1):
                row = np.zeros(frames, complex)
                scale = (float(z['amplitude'])*float(z['weights'][k]) *
                         math.sqrt(1 if k in (0, size//2) else 2)/math.sqrt(size))
                for j in range(size):
                    phase = -2*math.pi*k*j/size
                    row[int(start)+j] = (scale*float(z['window'][j]) /
                        math.sqrt(float(z['coverage'][int(start)+j])) *
                        complex(math.cos(phase), math.sin(phase)))
                rows.extend((row.real, row.imag))
        return np.eye(frames)/float(z['sigma'])**2+np.array(rows).T@np.array(rows)

    def scalar_cholesky(W):
        L = np.zeros_like(W)
        for i in range(len(W)):
            for j in range(i+1):
                value = float(W[i, j])-math.fsum(float(L[i, k])*float(L[j, k]) for k in range(j))
                L[i, j] = math.sqrt(value) if i == j else value/L[j, j]
        return L

    try:
        source = load(consume(a.study/'report.json'))
        old = load(consume(a.original_audit/'report.json'))
        assert source['backend'] == 'banded' and source['shared_rhs']
        assert old['result'] == 'independent_waveform_structured_controls_passed' and old['all_qualified']
        assert old['producer_sha256'] == sha(a.study/'report.json')
        for name, digest in source['sources'].items():
            assert sha(consume(a.study/'exact_sources'/name)) == digest
        for name in ('tools/waveform_banded_v1/metric.py', 'tools/waveform_banded_v1/root.py',
                     'tools/waveform_structured_v1/resources.py'):
            assert sha(consume(repo/name)) == source['sources'][name]
            dest = a.out/'exact_exercised_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
        for case in source['frames']:
            path = consume(a.study/case['file'])
            assert sha(path) == case['sha256']
            with np.load(path) as z:
                W = scalar_metric(z)
                L = scalar_cholesky(W)
                packedW, packedL = unpack(z['metric_bands'], True), unpack(z['root_bands'])
                check('all_scalar_DFT_entries', packedW, W)
                check('all_scalar_Cholesky_entries', packedL, L)
                check('complete_root_identity', packedL@packedL.T, W)
                probe = z['probe']
                for name, expected in (
                    ('band_apply', L@probe), ('band_transpose', L.T@probe),
                    ('band_inverse', np.linalg.solve(L, probe)),
                    ('band_inverse_transpose', np.linalg.solve(L.T, probe))):
                    check('saved_'+name, z[name], expected)
                metric = BandedMetric(np.array(z['metric_bands'], order='F', copy=True))
                check('symmetric_band_vector', metric@probe[:, 0], W@probe[:, 0])
                check('symmetric_band_matrix', metric@np.eye(len(W)), W)
                ledger = ArrayLedger()
                root = metric.factor(ledger)
                assert root.shares_input and np.shares_memory(root.L, metric.bands)
                factor_before = root.L.copy()
                rng = np.random.default_rng(72185)
                dense = rng.normal(size=(len(W), 6))
                isolated = np.column_stack((dense[:, 0], np.zeros(len(W))))
                layouts = dict(all_basis=np.eye(len(W)), vector=dense[:, 0],
                    C_order=np.array(dense[:, :3], order='C'),
                    F_order=np.array(dense[:, :3], order='F'),
                    strided=dense[:, ::2], isolated_right=isolated)
                aliases = []
                for layout, x in layouts.items():
                    before = x.copy()
                    for method, expected in (
                        ('apply', L@x), ('transpose', L.T@x),
                        ('solve', np.linalg.solve(L, x)),
                        ('solve_transpose', np.linalg.solve(L.T, x))):
                        got = getattr(root, method)(x)
                        check('live_'+method, got, expected)
                        assert np.array_equal(x, before) and not np.shares_memory(got, x)
                        assert np.array_equal(root.L, factor_before)
                        if layout == 'isolated_right':
                            assert np.count_nonzero(got[:, 1]) == 0
                    # Exercise the actual per-column native ABI, separately
                    # from the wrapper, so overwrite flags alone aren't proof.
                    rhs = np.array(dense[:, :3], order='F')
                    for native in ('tbmv', 'tbsv'):
                        for transpose in (0, 1):
                            xcol = rhs[:, 0].copy()
                            before_native = xcol.copy()
                            out = getattr(root, native)(root.bandwidth, root.L, xcol,
                                lower=1, trans=transpose, overwrite_x=1)
                            shares = bool(np.shares_memory(out, xcol))
                            assert shares
                            matrix = L.T if transpose else L
                            expected = (matrix@before_native if native == 'tbmv'
                                        else np.linalg.solve(matrix, before_native))
                            check('native_'+native, out, expected)
                            aliases.append(dict(layout=layout, native=native,
                                transpose=transpose, output_shares_input=shares))
                check('root_energy', np.sum(probe*(W@probe), axis=0),
                      np.sum(root.transpose(probe)**2, axis=0))
                for operation in (lambda: metric@probe, lambda: metric.factor(ledger)):
                    try:
                        operation()
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('Consumed metric unexpectedly reused')
                r['cases'].append(dict(label=case['label'], frames=len(W),
                    bandwidth=root.bandwidth, all_entries=len(W)**2,
                    all_basis_directions=len(W), saved_three_independent_RHS=True,
                    layouts=list(layouts), no_input_or_factor_mutation=True,
                    native_aliases=aliases, Cholesky_shares_input=root.shares_input,
                    resources=ledger.report(), qualified=True))
        assert len(r['cases']) == 4
        r.update(result='independent_waveform_banded_controls_passed', all_qualified=True,
            producer_sha256=sha(a.study/'report.json'),
            original_audit_sha256=sha(a.original_audit/'report.json'), auditor_sha256=sha(__file__),
            source_or_full_or_runtime_or_hearing_qualified=False)
        save(a.out/'report.json', r)
        print(r['result'], len(r['cases']), max(r['maximum_errors'].values()), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
