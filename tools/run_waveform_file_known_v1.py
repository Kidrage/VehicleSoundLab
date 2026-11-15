"""Rebuild SAMEoriginal12/shared8 through bounded file factors and original FFT."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import time
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'prerequisite', 'panel-audit', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--kind', choices=('original12', 'shared8'), required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from waveform_structured_v1.resources import ArrayLedger, process_memory
    from waveform_file_v1.pipeline import solve_corrected_file
    from waveform_banded_v1.metric import BandedMetric, supported_banded
    from waveform_correction_v1.problem import restore, evaluate
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', kind=a.kind, pid=os.getpid(), cases=[], sources={}, inputs={},
        material_read=False, fixed_correction_steps=2, inverse_backend='bounded_file',
        pipeline=False, file_pipeline=True)
    def bind(path):
        r['inputs'][str(path)] = sha(path)
        return load(path)
    try:
        audit = bind(a.prerequisite/'report.json')
        assert audit['result'] == 'independent_waveform_original_correction_controls_passed' and audit['all_qualified']
        panel = bind(a.panel_audit/'report.json')
        assert panel['all_qualified'] and panel['result'] == 'independent_waveform_file_panels_known_verified'
        root = a.workspace/'baselines/waveform_banded_v1'
        manifest = bind(root/'manifest.json')
        assert sha(root/'manifest.json') == load(repo/'research/waveform_banded_v1_summary.json')['manifest_sha256']
        entries = {row['path']:row['sha256'] for row in manifest['files']}
        study = root/'evidence'/('known1' if a.kind == 'original12' else 'shared1')
        source = bind(study/'report.json')
        assert r['inputs'][str(study/'report.json')] == entries[(study/'report.json').relative_to(root).as_posix()]
        names = set(source['sources'])
        names.update(('tools/run_waveform_file_known_v1.py', 'tools/waveform_correction_v1/problem.py',
            'tools/waveform_correction_v1/correct.py', 'tools/waveform_correction_v1/pipeline.py',
            'tools/waveform_structured_v1/resources.py', 'research/waveform_file_panels_v1_plan.json'))
        names.update(p.relative_to(repo).as_posix() for p in (repo/'tools/waveform_file_v1').glob('*.py'))
        for name in sorted(names):
            path = a.out/'exact_sources'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, path)
            r['sources'][name] = sha(path)
        for case in source['cases']:
            started = time.perf_counter()
            file = study/case['file']
            digest = sha(file)
            assert digest == case['sha256'] == entries[file.relative_to(root).as_posix()]
            r['inputs'][str(file)] = digest
            with np.load(file) as z:
                base = {name:z[name] for name in ('audio', 'positions', 'orders', 'scale', 'original')}
            system, prior, forward, adjoint, metric_action = restore(a.kind, case, base)
            if system.nsize > 512:
                raise ValueError('Known-only fixture runner cannot become a full/source runner')
            if case['kind'] == 'algebra':
                W = system.wave_metric
                if a.kind == 'shared8':
                    W = W[::base['audio'].shape[1], ::base['audio'].shape[1]]
                factory = lambda:BandedMetric.control_from_dense(W)
            else:
                factory = lambda:supported_banded(system.metric)
            target = base['audio'] if a.kind == 'shared8' else base['audio'].ravel()
            ledger = ArrayLedger()
            directory = a.out/(case['kind']+'_'+case['label']+'_factors')
            directory.mkdir()
            corrected, inverse, pipeline, initial, tau = solve_corrected_file(
                forward, adjoint, prior, factory, target, metric_action, directory, ledger, case['solver']['block'])
            original, stats = evaluate(system, base['audio'], corrected, base['original'], a.kind)
            if a.kind == 'shared8' and case['label'] == 'silent_right':
                assert np.count_nonzero(corrected['q'][:, 1]) == np.count_nonzero(corrected['wave_model_residual'][:, 1]) == 0
            if case['label'] == 'both_zero':
                assert np.count_nonzero(corrected['q']) == 0
            exports = inverse.audit_arrays()
            inverse.close()
            path = a.out/(case['kind']+'_'+case['label']+'.npz')
            np.savez_compressed(path, **base, **corrected, **original, **exports,
                **{'pipeline_base_'+name:value for name, value in initial.items()}, file_x_tau=tau)
            r['cases'].append(dict(label=case['label'], kind=case['kind'], file=path.name, sha256=sha(path),
                base_file=str(file), pipeline_info=pipeline, factor=inverse.info(), resources=ledger.report(),
                process_memory=process_memory(), elapsed_seconds=time.perf_counter()-started,
                previous_qualified=case['qualified'], **stats))
            save(a.out/'report.json', r)
            print('FILE PIPELINE', a.kind, case['label'], 'qualified', stats['qualified'],
                  'stable', stats['stable_complete_normal'], flush=True)
        count = 12 if a.kind == 'original12' else 8
        assert len(r['cases']) == count
        r.update(result='waveform_original_operator_correction_known_measured',
            all_qualified=all(c['qualified'] for c in r['cases']),
            pass_count=sum(c['qualified'] for c in r['cases']),
            full_or_real_or_C_or_hearing_qualified=False)
        save(a.out/'report.json', r)
        print('FILE KNOWN COMPLETE', r['pass_count'], flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
