"""Analytically streamed moderate matrices qualify the proposed1024 panels."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time
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
    from waveform_file_v1.store import FileMatrix
    from waveform_file_v1.factor import FileQR
    from waveform_file_v1.triangle import solve
    from waveform_structured_v1.resources import ArrayLedger, process_memory
    from run_waveform_stream_full_v1 import physical_memory
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), sources={}, inputs={}, cases=[], material_read=False)
    try:
        summary_path = repo/'research/waveform_file_panels_v1_summary.json'
        previous = load(summary_path)
        r['inputs'][str(summary_path)] = sha(summary_path)
        for name in ('independent_archive_verification', 'independent_binding_verification'):
            receipt = previous[name]
            assert sha(receipt['path']) == receipt['sha256']
            r['inputs'][receipt['path']] = receipt['sha256']
        names = {'tools/run_waveform_file_panel_probe_v1.py', 'tools/run_waveform_stream_full_v1.py',
            'tools/waveform_structured_v1/resources.py', 'research/waveform_file_full_v1_plan.json'}
        for path in (repo/'tools/waveform_file_v1').glob('*.py'):
            name = path.relative_to(repo).as_posix()
            assert sha(path) == previous['current_source_sha256'][name]
            names.add(name)
        for name in sorted(names):
            path = a.out/'exact_sources'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, path)
            r['sources'][name] = sha(path)
        memory = physical_memory()
        required = 128*1024**2 + 4*8*2305*1024 + 3*1024**3//2 + 3*1024**3
        r['preflight'] = dict(**memory, required_available=required,
            passed=min(memory['available_physical_bytes'], memory['available_commit_bytes']) >= required)
        if not r['preflight']['passed']:
            raise MemoryError('Moderate panel probe preflight failed')
        for m, n in ((2305, 1537), (1537, 2305)):
            started = time.monotonic()
            label = f'{m}x{n}'
            ledger = ArrayLedger()
            matrix = FileMatrix(a.out/(label+'.bin'), (m, n), 1024, ledger)
            i = np.arange(m)[:, None] + 1.
            for first in range(0, n, 1024):
                last = min(first+1024, n)
                j = np.arange(first, last)[None] + 1.
                panel = np.array(.03*np.cos(.0031*i*j)+.02*np.sin(.0023*(2*i-1)*j), order='F')
                for column in range(first, min(last, m)):
                    panel[column, column-first] += 1+.2*np.cos(column+1.)
                ledger.add('probe.analytic_input_panel', panel)
                matrix.write(0, m, first, last, panel)
                ledger.snapshot('probe.analytic_panel.written')
                del panel
            qr = FileQR(matrix)
            indices = np.unique(np.r_[0, 1, 511, 1023, 1024, min(m, n)-1, n-1]).astype(int)
            R = np.zeros((m, len(indices)), order='F')
            ledger.add('probe.selected_R_columns', R)
            for col, j in enumerate(indices):
                panel = matrix.read(0, min(m, n), int(j), int(j)+1)
                R[:min(m, n), col] = panel[:, 0]
                R[min(int(j)+1, m):, col] = 0.
            roundtrip = qr.apply(R)
            rows = np.arange(m)+1.
            rhs = np.column_stack((np.sin(.1*rows), np.cos(.07*rows), np.zeros(m)))
            forward, transpose = qr.apply(rhs), qr.apply(rhs, True)
            extras = {}
            if m >= n:
                rows = np.arange(n)+1.
                exact = np.column_stack((np.sin(.09*rows), np.cos(.08*rows), np.zeros(n)))
                b = np.zeros_like(exact)
                bt = np.zeros_like(exact)
                for first in range(0, n, 1024):
                    last = min(first+1024, n)
                    upper = matrix.read(0, n, first, last)
                    for j in range(first, last):
                        upper[j+1:, j-first] = 0.
                    b += upper@exact[first:last]
                    bt[first:last] = upper.T@exact
                extras = dict(triangular_exact=exact, triangular_rhs=b, triangular_transpose_rhs=bt,
                    triangular_forward=solve(qr, b), triangular_transpose=solve(qr, bt, True))
            matrix.close()
            path = a.out/(label+'.npz')
            np.savez_compressed(path, indices=indices, tau=qr.tau, selected_R=R,
                roundtrip=roundtrip, rhs=rhs, forward=forward, transpose=transpose, **extras)
            r['cases'].append(dict(label=label, file=path.name, sha256=sha(path), factor=qr.report(),
                resources=ledger.report(), process_memory=process_memory(), elapsed_seconds=time.monotonic()-started))
            save(a.out/'report.json', r)
            print('LARGE FILE PANEL', label, 'elapsed', r['cases'][-1]['elapsed_seconds'], flush=True)
        r.update(result='waveform_file_large_panels_measured', block=1024,
            no_full_or_real_or_runtime_qualification=True)
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error), process_memory=process_memory())
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
