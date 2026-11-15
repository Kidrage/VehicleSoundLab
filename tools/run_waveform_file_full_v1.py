"""ONE preflight-gated SAMEfull12289/49/288 independent-stereo file solve."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original', 'prerequisite', 'panel-audit', 'base-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_supported_v1.metric import SupportedMetric
    from observer_supported_v1.fit import SupportedSystem
    from waveform_stream_v1.shared import SharedSupportedGeometry
    from waveform_banded_v1.metric import supported_banded
    from waveform_structured_v1.resources import process_memory
    from waveform_file_full_v1.resources import preflight, Telemetry
    from waveform_file_full_v1.pipeline import solve_full
    from waveform_file_full_v1.evaluate import evaluate
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    r = dict(result='running', pid=os.getpid(), sources={}, inputs={}, only_one_attempt=True,
        material_read=False, file_pipeline=True, block=1024)
    ledger = Telemetry(a.out)
    def read(path):
        r['inputs'][str(path)] = sha(path)
        return load(path)
    try:
        summary = read(repo/'research/waveform_file_panels_v1_summary.json')
        assert a.prerequisite == a.workspace/'baselines/waveform_file_panels_v1'
        assert sha(a.prerequisite/'manifest.json') == summary['manifest_sha256']
        read(a.prerequisite/'manifest.json')
        for key in ('independent_archive_verification', 'independent_binding_verification'):
            receipt = summary[key]
            assert sha(receipt['path']) == receipt['sha256']
            r['inputs'][receipt['path']] = receipt['sha256']
        for folder in ('controls_audit3', 'panels_audit2', 'known_audit1', 'shared_audit1', 'resources_audit1'):
            receipt = read(a.prerequisite/'evidence'/folder/'report.json')
            assert receipt['all_qualified']
        panel = read(a.panel_audit/'report.json')
        assert panel['all_qualified'] and panel['result'] == 'independent_waveform_file_large_panels_verified' and panel['block'] == 1024
        panel_source_path = a.panel_audit.parent/'panels1/report.json'
        panel_source = read(panel_source_path)
        assert panel['producer_sha256'] == sha(panel_source_path)
        for name, digest in panel_source['sources'].items():
            assert sha(repo/name) == digest
        base_audit = read(a.base_audit/'report.json')
        assert base_audit['all_qualified'] and base_audit['result'] == 'independent_waveform_file_base_guard_verified'
        for name, digest in base_audit['sources'].items():
            assert sha(repo/name) == digest
        for name, digest in base_audit['inputs'].items():
            assert sha(name) == digest
        for path in (repo/'tools/waveform_file_v1').glob('*.py'):
            assert sha(path) == summary['current_source_sha256'][path.relative_to(repo).as_posix()]
        root = a.workspace/'baselines/waveform_stream_full_v1'
        assert a.original == root/'evidence/full1'
        assert sha(root/'manifest.json') == read(repo/'research/waveform_stream_full_v1_summary.json')['manifest_sha256']
        manifest = read(root/'manifest.json')
        mapping = {row['path']:row['sha256'] for row in manifest['files']}
        original = read(a.original/'report.json')
        assert sha(a.original/'report.json') == mapping['evidence/full1/report.json']
        assert original['solver_qualified'] and original['fidelity_qualified']
        assert sha(a.original/'capture.npz') == original['capture_sha256'] == mapping['evidence/full1/capture.npz']
        r['inputs'][str(a.original/'capture.npz')] = sha(a.original/'capture.npz')
        names = set(original['sources'])
        for folder in ('waveform_file_v1', 'waveform_file_full_v1', 'waveform_correction_v1', 'waveform_banded_v1',
                       'waveform_stream_v1', 'waveform_structured_v1', 'observer_supported_v1',
                       'observer_complete_v1', 'observer_representer_v1'):
            names.update(p.relative_to(repo).as_posix() for p in (repo/'tools'/folder).glob('*.py'))
        names.update(('tools/run_waveform_file_full_v1.py', 'tools/run_waveform_stream_full_v1.py',
            'tools/audit_waveform_file_full_v1.py', 'research/waveform_file_full_v1_plan.json'))
        for name in sorted(names):
            path = a.out/'exact_sources'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, path)
            r['sources'][name] = sha(path)
        with np.load(a.original/'capture.npz') as z:
            capture = {name:z[name] for name in ('audio', 'positions', 'orders', 'scale', 'nodes', 'factors', 'loadings')}
        audio, positions, orders, scale = (capture[name] for name in ('audio', 'positions', 'orders', 'scale'))
        assert audio.shape == (12289, 2) and len(positions) == 49 and len(orders) == 288
        r['resource_preflight'] = preflight(a.out)
        save(a.out/'report.json', r)
        if not r['resource_preflight']['memory_passed'] or not r['resource_preflight']['disk_passed']:
            raise MemoryError('Complete file preflight failed before matrix/file allocation')
        synthesis = WaveSynthesis(len(audio), positions, orders, 2)
        metric = SupportedMetric(audio, 64.)
        system = SupportedSystem(synthesis, scale, metric)
        shared = SharedSupportedGeometry(system)
        directory = a.out/'factors'
        directory.mkdir()
        action = lambda e:e/metric.wave_scale**2+metric.adjoint(metric.forward(e))
        ledger.snapshot('fullPipeline.before_metric')
        values, inverse, pipeline, initial, taus = solve_full(shared, lambda:supported_banded(metric), audio,
            action, directory, ledger, 1024)
        inverse.close()
        inverse_info = inverse.info()
        outputs, stats = evaluate(system, shared, audio, values, pipeline['base_solver'])
        ledger.snapshot('fullPipeline.evaluated')
        capture.update(values, **outputs, **taus, inverse_right_tau=inverse.right.tau,
            inverse_inner_tau=inverse.inner.tau, **{'base_'+name:value for name, value in initial.items()})
        np.savez_compressed(a.out/'capture.npz', **capture)
        comparisons = []
        for name, value in stats['metrics'].items():
            now = value if isinstance(value, list) else [value]
            old = original['metrics'][name]
            old = old if isinstance(old, list) else [old]
            comparisons.extend(dict(metric=name, index=i, previous=x, current=y, regressed=y > x)
                               for i, (x, y) in enumerate(zip(old, now)))
        assert len(comparisons) == 17
        ledger.snapshot('fullPipeline.saved')
        r.update(result='waveform_file_full_known_measured', pipeline=pipeline, solver=pipeline['base_solver'],
            inverse_info=inverse_info, comparison_rows=comparisons, **stats,
            capture_sha256=sha(a.out/'capture.npz'), resources=ledger.report(), process_memory=process_memory(),
            solve_wall_seconds=time.monotonic()-started,
            no_full_factor_arrays_in_capture=True, independently_qualified=False,
            no_real_source_or_C_or_hearing_qualification=True)
        save(a.out/'report.json', r)
        ledger.progress(dict(pid=os.getpid(), status='completed', elapsed_seconds=time.monotonic()-started,
            report_sha256=sha(a.out/'report.json')))
        print('FILE_FULL_COMPLETE', stats['solver_qualified'], stats['fidelity_qualified'],
              stats['original_stable_complete_normal'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error), process_memory=process_memory())
        save(a.out/'report.json', r)
        ledger.progress(dict(pid=os.getpid(), status='failed', error=repr(error),
            report_sha256=sha(a.out/'report.json'), elapsed_seconds=time.monotonic()-started))
        raise


if __name__ == '__main__':
    main()
