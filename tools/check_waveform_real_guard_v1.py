"""Direct all-bin DFT and dense triangular controls for the new audit only."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from waveform_real_guard_v1.locked import metric_bands, factor, root_action
    a.out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    r = dict(result='running', cases=[], sources={})
    for name in ('tools/check_waveform_real_guard_v1.py', 'tools/waveform_real_guard_v1/locked.py'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(dest)
    try:
        rng = np.random.default_rng(920483)
        for size in (16, 32):
            hop, N = size//4, 2*size+3
            window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
            cover = np.zeros(N)
            for start in range(-(size-hop), N, hop):
                first, last = max(0, start), min(N, start+size)
                cover[first:last] += window[first-start:last-start]**2
            weights = np.exp(rng.uniform(-1., 1., size//2+1))
            sigma, amplitude = .37, 1.83
            W = np.eye(N)/sigma**2
            endpoint = np.r_[1., np.full(size//2-1, np.sqrt(2.)), 1.]
            dft = np.exp(-2j*np.pi*np.arange(size//2+1)[:, None]*np.arange(size)[None]/size)
            for start in range(0, N-size+1, hop):
                A = dft*(window/np.sqrt(cover[start:start+size]))[None]
                A *= (endpoint*amplitude*weights/np.sqrt(size))[:, None]
                W[start:start+size, start:start+size] += (A.conj().T@A).real
            bands = metric_bands(N, weights, sigma, amplitude, size=size, hop=hop)
            rebuilt = np.zeros((N, N))
            for offset in range(size):
                i = np.arange(N-offset)
                rebuilt[i+offset, i] = bands[offset, :N-offset]
                rebuilt[i, i+offset] = bands[offset, :N-offset]
            matrix_error = float(np.max(abs(rebuilt-W))/np.max(abs(W)))
            assert matrix_error < 2e-12
            root = factor(bands)
            dense = linalg.cholesky(W, lower=True)
            x = rng.standard_normal((N, 2))
            errors = {}
            for tag, got, wanted in (
                ('lower', root_action(root, x), dense@x),
                ('transpose', root_action(root, x, transpose=True), dense.T@x),
                ('metric', root_action(root, root_action(root, x, transpose=True)), W@x)):
                errors[tag] = float(np.max(abs(got-wanted))/max(float(np.max(abs(wanted))), 1e-300))
                assert errors[tag] < 2e-12, (tag, errors[tag])
            bad = []
            for tag, args in (
                ('missing_bin', (N, weights[:-1], sigma, amplitude)),
                ('zero_scale', (N, weights, 0., amplitude)),
                ('nonfinite_weight', (N, weights*np.nan, sigma, amplitude))):
                try:
                    metric_bands(*args, size=size, hop=hop)
                except ValueError:
                    bad.append(tag)
                else:
                    raise AssertionError('Invalid metric accepted: '+tag)
            r['cases'].append(dict(size=size, frames=N, full_DFT_matrix_relative_error=matrix_error,
                root_action_relative_errors=errors, invalid_rejections=bad))
        r.update(result='independent_locked_metric_direct_DFT_controls_verified', all_qualified=True,
            gates_unchanged=True, no_real_fit_or_voice_qualification=True)
        save(a.out/'report.json', r)
        print(r['result'], len(r['cases']), flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
