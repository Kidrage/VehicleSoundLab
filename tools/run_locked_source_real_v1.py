"""Fit ONE never-fitted full real source, then independently audit it and stop."""
import argparse
import gc
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from research_archive_v1 import load, save, sha


LABELS = ('F3 Fifth First Mid', 'F3 Fifth First Late', 'F3 Fifth Second Early',
          'F3 Fifth Second Mid', 'F3 Fifth Second Late')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'preparation', 'preparation-audit', 'known-audit', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--label', choices=LABELS, default=LABELS[0])
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_fit_v1.adapter import build
    from waveform_file_real_v1.evaluate import evaluate
    from waveform_file_real_v1.resources import preflight
    from waveform_file_full_v1.pipeline import solve_full
    from waveform_file_full_v1.resources import Telemetry
    from waveform_banded_v1.metric import supported_banded
    from waveform_structured_v1.resources import process_memory

    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = dict(result='running', pid=os.getpid(), cases=[], sources={}, inputs={}, block=1024,
                  only_one_finite_case=True, new_method='sinc128 source, unchanged explicit legacy metric_target')

    def read(path):
        path = Path(path); report['inputs'][str(path)] = sha(path)
        return load(path)

    try:
        preparation = read(args.preparation/'report.json')
        pa = read(args.preparation_audit/'report.json')
        known = read(args.known_audit/'report.json')
        assert preparation['result'] == 'locked_source_five_prepared' and len(preparation['cases']) == 5
        assert pa['result'] == 'independent_locked_source_preparation_verified' and pa['all_qualified']
        assert pa['producer_sha256'] == sha(args.preparation/'report.json') and len(pa['cases']) == 5
        assert known['result'] == 'independent_locked_source_known_verified' and known['all_qualified']
        assert len(known['cases']) == 4 and args.label in LABELS
        assert [row['label'] for row in preparation['cases']] == list(LABELS)
        for source in (preparation, known):
            for name, wanted in source.get('sources', {}).items(): assert sha(repo/name) == wanted
            for path, wanted in source['inputs'].items():
                assert sha(path) == wanted; report['inputs'][path] = wanted
        assert not (args.workspace/'references/analysis/waveform_file_real_v1/real1'/args.label).exists()
        # Prior attempts are not permission to repeat the same fitted segment.
        root = args.workspace/'references/analysis/locked_source_fit_v1'
        for path in root.glob('*/run_spec.json'):
            old = load(path)
            if old.get('schema') == 'vsl.locked_source_real_spec/1':
                assert args.label not in old['declared_cases'], ('Already attempted', args.label, str(path))
        row = next(row for row in preparation['cases'] if row['label'] == args.label)
        prepared = args.preparation/row['file']
        assert sha(prepared) == row['sha256']; read_path = str(prepared)
        report['inputs'][read_path] = row['sha256']
        disk = sum(row['resources']['full_factor_disk_bytes'] for row in preparation['cases'])
        assert disk == preparation['retained_five_factor_bytes'] and shutil.disk_usage(args.out).free >= disk+2*1024**3
        names = set(preparation['sources']) | {'tools/run_locked_source_real_v1.py',
            'tools/audit_locked_source_real_v1.py', 'tools/research_archive_v1.py'}
        for name in sorted(names):
            dest = args.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); report['sources'][name] = sha(dest)
        spec = dict(schema='vsl.locked_source_real_spec/1', pid=os.getpid(), declared_cases=[args.label],
            prepared_labels=list(LABELS), sources=report['sources'], inputs=report['inputs'],
            only_one_finite_case=True, block=1024, retained_five_factor_bytes=disk,
            prepared_file=str(prepared), prepared_sha256=row['sha256'],
            known_audit=str(args.known_audit/'report.json'),
            original_first_case_excluded=True, stop_after_terminal_case_before_later_fits=True)
        save(args.out/'run_spec.json', spec); save(args.out/'report.json', report)
        directory = args.out/args.label; directory.mkdir()
        with np.load(prepared) as saved: z = {name: saved[name] for name in saved.files}
        system, shared, reference = build(z['audio'], z['target'], z['metric_target'], z['original_positions'], z['orders'], z['scale'])
        metric = system.metric
        assert np.array_equal(z['positions'], system.synthesis.positions)
        for name in ('weights', 'band_power', 'floor_active'): assert np.array_equal(z[name], getattr(metric, name))
        assert float(z['sigma']) == metric.wave_scale and float(z['amplitude']) == metric.amplitude_scale
        resources = preflight(directory, len(z['audio']), len(z['positions']), 288, 1024)
        save(directory/'preflight.json', resources)
        if not resources['memory_passed'] or not resources['disk_passed']:
            raise MemoryError('Original full geometry/reserves failed; no factor allocation permitted')
        ledger = Telemetry(directory); factors = directory/'factors'; factors.mkdir()
        print('LOCKED_REAL_PID', os.getpid(), args.label, 'N', len(z['audio']), 'M', len(z['positions']), flush=True)
        action = lambda error: error/metric.wave_scale**2+metric.adjoint(metric.forward(error))
        values, inverse, pipeline, initial, taus = solve_full(shared, lambda: supported_banded(metric),
            z['audio'], action, factors, ledger, 1024)
        inverse.close(); inverse_info = inverse.info()
        outputs, stats = evaluate(system, shared, z['audio'], values, pipeline['base_solver'], reference)
        ledger.snapshot('fullPipeline.evaluated')
        z.update(values, **outputs, **taus, inverse_right_tau=inverse.right.tau, inverse_inner_tau=inverse.inner.tau,
                 **{'base_'+name: value for name, value in initial.items()})
        np.savez_compressed(directory/'capture.npz', **z)
        ledger.snapshot('fullPipeline.saved')
        info = dict(result='locked_source_real_case_measured', label=args.label, frames=len(z['audio']),
            nodes=len(z['positions']), orders=288, block=1024, pipeline=pipeline, solver=pipeline['base_solver'],
            inverse_info=inverse_info, **stats, resource_preflight=resources, resources=ledger.report(),
            process_memory=process_memory(), capture_sha256=sha(directory/'capture.npz'),
            prepared_file=str(prepared), prepared_sha256=row['sha256'],
            no_full_factor_arrays_in_capture=True, no_sustained_source_or_C_or_hearing_promotion=True,
            process_peak_is_cumulative_not_isolated_case=True)
        save(directory/'report.json', info)
        ledger.progress(dict(pid=os.getpid(), status='completed', label=args.label, report_sha256=sha(directory/'report.json')))
        del z, values, inverse, outputs, system, shared, reference, initial, taus, pipeline, metric, action
        gc.collect()
        audited_dir = args.out/(args.label+'_audit')
        subprocess.run([sys.executable, str(repo/'tools/audit_locked_source_real_v1.py'),
            '--workspace', str(args.workspace), '--study', str(directory), '--out', str(audited_dir)], check=True, cwd=repo)
        audited = load(audited_dir/'report.json'); assert audited['verification_passed']
        report['cases'].append(dict(label=args.label, case_report=args.label+'/report.json',
            case_report_sha256=sha(directory/'report.json'), audit_report=audited_dir.name+'/report.json',
            audit_report_sha256=sha(audited_dir/'report.json'), solver_qualified=audited['case']['solver_qualified'],
            fidelity_qualified=audited['case']['fidelity_qualified'], metrics=audited['case']['metrics']))
        report.update(result='locked_source_one_real_measured', verification_passed=True,
            elapsed_seconds_PC_only=time.monotonic()-started, no_automatic_next_fit=True,
            no_C_or_hearing_or_sustained_promotion=True)
        save(args.out/'report.json', report)
        print('LOCKED_REAL_COMPLETE', args.label, report['cases'][0]['solver_qualified'], report['cases'][0]['fidelity_qualified'], flush=True)
    except BaseException as error:
        report.update(result='failed', error=repr(error), elapsed_seconds_PC_only=time.monotonic()-started)
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__': main()
