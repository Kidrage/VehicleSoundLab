"""Exactly128 diagnostic steps of the identical frozen full operator, no solve."""
import argparse, os, shutil, sys, time
from pathlib import Path
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original', 'prerequisite', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem
    from observer_representer_v1.primal import PenaltyPrimal
    from krylov_diagnostic_v1.bidiagonal import probe
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', pid=os.getpid(), sources={}, inputs={}, material_read=False)
    try:
        original, gate = load(a.original/'report.json'), load(a.prerequisite/'report.json')
        assert original['result'] == 'observer_representer_full_known_measured'
        assert not original['solver_qualified'] and original['only_one_attempt']
        assert gate['result'] == 'independent_observer_krylov_known_passed'
        for path in (a.original/'report.json', a.original/'capture.npz', a.prerequisite/'report.json'):
            r['inputs'][str(path)] = sha(path)
        assert sha(a.original/'capture.npz') == original['capture_sha256']
        names = tuple(original['sources'])+('tools/run_observer_krylov_full_v1.py',
            'tools/krylov_diagnostic_v1/bidiagonal.py', 'research/observer_representer_krylov_v1_plan.json')
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        with np.load(a.original/'capture.npz') as z:
            audio, positions, orders, scale = (z[n] for n in ('audio', 'positions', 'orders', 'scale'))
        system = SupportedSystem(WaveSynthesis(len(audio), positions, orders, 2), scale, SupportedMetric(audio, 64.))
        op = PenaltyPrimal(system)
        rhs = np.r_[system.rhs(audio)[:system.ysize], np.zeros(system.nsize)]
        print('KRYLOV_FULL_PID', os.getpid(), op.shape, flush=True)
        started = time.monotonic()
        capture, info = probe(op, rhs, 128)
        elapsed = time.monotonic()-started
        files = {}
        for name in ('U', 'V'):
            dest = a.out/('basis_'+name+'.npy')
            np.save(dest, capture.pop(name))
            files[dest.name] = sha(dest)
        dest = a.out/'coefficients.npz'
        np.savez_compressed(dest, **capture)
        files[dest.name] = sha(dest)
        r.update(result='observer_krylov_full_diagnostic_measured', info=info, files=files,
            probe_wall_seconds=elapsed, operator_shape=list(op.shape), only_one_fixed128_probe=True,
            no_new_solution_or_material_fit_or_runtime_change=True)
        save(a.out/'report.json', r)
        print(r['result'], info, flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
