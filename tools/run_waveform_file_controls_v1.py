"""Known-only file QR kernels, original8 inverse and original7 corrections."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time
from research_archive_v1 import save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    a = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from waveform_structured_v1.resources import ArrayLedger, process_memory
    from waveform_file_v1.store import FileMatrix
    from waveform_file_v1.factor import FileQR
    from waveform_file_v1.triangle import solve
    from waveform_file_v1.inverse import FileNormalInverse
    from waveform_file_v1.graph import solve_graph
    from waveform_correction_v1.fixtures import inverse_fixtures
    from waveform_correction_v1.correct import refine
    from waveform_representer_v1.fixtures import algebra_fixtures
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', kernel_cases=[], inverse_cases=[], original_cases=[],
        sources={}, material_read=False, inverse_backend='bounded_file',
        whole_file_mapping=False, full_or_source_or_runtime_qualification=False)
    names = {'tools/run_waveform_file_controls_v1.py',
        'research/waveform_file_panels_v1_plan.json',
        'tools/waveform_correction_v1/fixtures.py', 'tools/waveform_correction_v1/correct.py',
        'tools/waveform_representer_v1/fixtures.py', 'tools/waveform_structured_v1/resources.py'}
    names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/waveform_file_v1').glob('*.py'))
    for name in sorted(names):
        path = a.out/'exact_sources'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, path)
        report['sources'][name] = sha(path)
    class Prior:
        def __init__(self, R):
            self.L = np.linalg.cholesky(R)
        def inverse_transpose(self, value):
            return linalg.solve_triangular(self.L, value, trans='T', lower=True)
        def inverse(self, value):
            return linalg.solve_triangular(self.L, value, lower=True)
    def store(root, value, block, ledger):
        root.mkdir()
        return FileMatrix.from_array(root/'source.bin', np.array(value, dtype='float64'), block, ledger)
    def files(root):
        return [dict(file=p.relative_to(a.out).as_posix(), bytes=p.stat().st_size,
                     sha256=sha(p)) for p in sorted(root.glob('*.bin'))]
    started = time.perf_counter()
    try:
        rng = np.random.default_rng(934798)
        for shape in ((13, 8), (8, 13), (9, 9)):
            for block in (1, 3, 4, 16):
                label = '%dx%d_b%d' % (*shape, block)
                root = a.out/('kernel_'+label)
                ledger = ArrayLedger()
                X = rng.normal(size=shape)
                matrix = store(root, X, block, ledger)
                qr = FileQR(matrix)
                raw = matrix.audit_array()
                rhs = np.column_stack((np.eye(shape[0]), rng.normal(size=(shape[0], 3)), np.zeros(shape[0])))
                forward, backward = qr.apply(rhs), qr.apply(rhs, True)
                extras = {}
                if shape[0] >= shape[1]:
                    b = rng.normal(size=(shape[1], 3))
                    extras = dict(triangular_rhs=b, triangular_forward=solve(qr, b),
                                  triangular_transpose=solve(qr, b, True))
                matrix.close()
                path = a.out/('kernel_'+label+'.npz')
                np.savez_compressed(path, X=X, x_raw=raw, x_tau=qr.tau, rhs=rhs,
                    forward=forward, transpose=backward, **extras)
                report['kernel_cases'].append(dict(label=label, file=path.name, sha256=sha(path),
                    factor=qr.report(), resources=ledger.report(), files=files(root)))
                print('FILE KERNEL', label, flush=True)
        for label, X, rhs in inverse_fixtures():
            ledger = ArrayLedger()
            root = a.out/('inverse_'+label)
            matrix = store(root, X, 3, ledger)
            source = FileQR(matrix)
            raw = matrix.audit_array()
            inverse = FileNormalInverse(source)
            got = inverse.apply(rhs)
            reverse = inverse.apply(rhs[:, X.shape[1]:X.shape[1]+2])
            exported = inverse.audit_arrays()
            inverse.close()
            matrix.close()
            path = a.out/('inverse_'+label+'.npz')
            np.savez_compressed(path, X=X, rhs=rhs, got=got, reverse=reverse,
                x_raw=raw, x_tau=source.tau, **exported)
            report['inverse_cases'].append(dict(label=label, file=path.name, sha256=sha(path),
                source_factor=source.report(), factor=inverse.info(), resources=ledger.report(), files=files(root)))
            print('FILE INVERSE', label, flush=True)
        rng = np.random.default_rng(471083)
        for label, P, W, R, y in algebra_fixtures():
            ledger = ArrayLedger()
            root = a.out/('original_'+label)
            prior = Prior(R)
            Lw = np.linalg.cholesky(W)
            X = linalg.solve_triangular(prior.L, (Lw.T@P).T, lower=True).T
            matrix = store(root, X, 3, ledger)
            source = FileQR(matrix)
            raw = matrix.audit_array()
            base, graph = solve_graph(source, Lw.T@y)
            base['q'] = prior.inverse_transpose(base['z'])
            base['wave_model_residual'] = linalg.solve_triangular(Lw, base['root_model_residual'], trans='T', lower=True)
            inverse = FileNormalInverse(source)
            delta = np.zeros_like(base['z']) if label == 'zero' else rng.normal(size=base['z'].shape)*.01
            corrected = refine(lambda x:P@x, lambda x:P.T@x, prior, lambda e:W@e, base, inverse, initial_delta=delta)
            exported = inverse.audit_arrays()
            inverse.close()
            graph.raw.close()
            matrix.close()
            path = a.out/('original_'+label+'.npz')
            np.savez_compressed(path, Phi=P, W=W, R=R, y=y, base_z=base['z'],
                base_wave=base['wave_model_residual'], initial_delta=delta,
                x_raw=raw, x_tau=source.tau, **corrected, **exported)
            report['original_cases'].append(dict(label=label, file=path.name, sha256=sha(path),
                source_factor=source.report(), graph_factor=graph.report(), factor=inverse.info(),
                resources=ledger.report(), files=files(root), fixed_correction_steps=2))
            print('FILE ORIGINAL CORRECTION', label, flush=True)
        assert len(report['kernel_cases']) == 12 and len(report['inverse_cases']) == 8 and len(report['original_cases']) == 7
        report.update(result='waveform_original_correction_controls_measured',
            file_kernel_stage=True, solve_wall_seconds=time.perf_counter()-started, process_memory=process_memory(),
            audit_exports_limited_to_512=True, original12_shared8_not_yet_tested=True)
        save(a.out/'report.json', report)
        print('FILE CONTROLS COMPLETE', report['solve_wall_seconds'], flush=True)
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        save(a.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
