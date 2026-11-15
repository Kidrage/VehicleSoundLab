"""Prepare five never-fitted sources with explicit immutable legacy calibration."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'known', 'known-audit', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_fit_v1.adapter import build
    from waveform_file_real_v1.resources import preflight
    from observer_inverse_v1.fit import complex_array

    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', cases=[], sources={}, inputs={}, no_inverse_fit=True,
                  nominal_sinc_radius=128, excluded_completed_case='F3 Fifth First Early')

    def read(path):
        path = Path(path); report['inputs'][str(path)] = sha(path)
        return load(path)

    def absorb(source):
        for name, wanted in source.get('sources', {}).items():
            assert sha(repo/name) == wanted, name
            report['sources'][name] = wanted
        for path, wanted in source.get('inputs', {}).items():
            assert sha(path) == wanted, path
            report['inputs'][path] = wanted

    try:
        known, audit = read(args.known/'report.json'), read(args.known_audit/'report.json')
        assert known['result'] == 'locked_source_fit_known_measured' and known['all_qualified']
        assert audit['result'] == 'independent_locked_source_known_verified' and audit['all_qualified']
        assert len(audit['cases']) == 4 and audit['producer_sha256'] == sha(args.known/'report.json')
        absorb(known); absorb(audit)
        for row in audit['cases']:
            if row['complete_audit_file']: read(args.known_audit/row['complete_audit_file'])

        original_root = args.workspace/'references/analysis/waveform_file_real_v1'
        original_spec = read(original_root/'real1/run_spec.json')
        assert len(original_spec['sources']) == 96 and len(original_spec['inputs']) == 71
        absorb(original_spec)
        read(original_root/'real1/report.json')
        original = read(original_root/'prepare1/report.json')
        original_audit = read(original_root/'prepare_audit1/report.json')
        assert original_audit['all_qualified'] and original_audit['producer_sha256'] == sha(original_root/'prepare1/report.json')
        absorb(original)
        resampling = args.workspace/'references/analysis/source_resampling_v1'
        replacement = read(resampling/'real1/report.json')
        source_audit = read(resampling/'real_audit1/report.json')
        assert replacement['result'] == 'source_resampling_six_actual_measured'
        assert source_audit['verification_passed'] and source_audit['producer_sha256'] == sha(resampling/'real1/report.json')
        absorb(replacement)
        assert len(original['cases']) == len(replacement['cases']) == 6

        prior = args.workspace/'baselines/source_resampling_v1/evidence'
        for filename, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
            values = read(prior/filename)
            assert len(values) == count and all(sha(repo/name) == wanted for name, wanted in values.items())
        report['protected_C_index_sha256'] = sha(repo/'handoff/C文件索引.csv')
        names = set(report['sources']) | {
            'tools/prepare_locked_source_real_v1.py', 'tools/audit_locked_source_preparation_v1.py',
            'research/locked_source_fit_v1_plan.json'}
        names.update(path.relative_to(repo).as_posix() for path in (repo/'tools/locked_source_fit_v1').glob('*.py'))
        for name in sorted(names):
            dest = args.out/'exact_sources'/name; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest); report['sources'][name] = sha(dest)

        for row in original['cases'][1:]:
            label = row['label']
            assert label != 'F3 Fifth First Early' and not (original_root/'real1'/label).exists()
            replacement_row = next(c for c in replacement['cases'] if c['label'] == label)
            old_path, source_path = original_root/'prepare1'/row['file'], resampling/'real1'/replacement_row['file']
            assert sha(old_path) == row['sha256'] and sha(source_path) == replacement_row['sha256']
            report['inputs'][str(old_path)] = sha(old_path); report['inputs'][str(source_path)] = sha(source_path)
            with np.load(old_path) as saved: z = {name: saved[name] for name in saved.files}
            with np.load(source_path) as saved: source = {name: saved[name] for name in saved.files}
            for name in ('positions', 'original_positions', 'orders', 'scale', 'source_coordinates', 'weights', 'amplitude', 'source_start'):
                assert np.array_equal(z[name], source[name]), name
            z['metric_target'] = z['target'].copy()
            z['audio'] = source['sinc128'].copy()
            z['target'] = z['audio'][2048:-2048].copy()
            system, shared, reference = build(z['audio'], z['target'], z['metric_target'], z['original_positions'], z['orders'], z['scale'])
            assert np.array_equal(z['positions'], system.synthesis.positions)
            metric = system.metric
            for name in ('weights', 'band_power', 'floor_active'):
                assert np.array_equal(z[name], getattr(metric, name)), name
            assert float(z['sigma']) == metric.wave_scale and float(z['amplitude']) == metric.amplitude_scale
            assert np.array_equal(z['orders'], np.arange(1, 289))
            z['probe_wave'] = system.synthesis.synthesize(complex_array(z['probe_q'], system.nshape)*z['scale'][None])
            z['probe_spectrum'] = metric.forward(z['probe_wave'])
            output = args.out/(label+'.npz'); np.savez_compressed(output, **z)
            resources = preflight(args.out, len(z['audio']), len(z['positions']), 288, 1024)
            report['cases'].append(dict(label=label, file=output.name, sha256=sha(output),
                original_preparation=str(old_path), source_query_file=str(source_path),
                frames=len(z['audio']), target_frames=len(z['target']), nodes=len(z['positions']), orders=288,
                metric_origin='explicit metric_target: unchanged original legacy target',
                resources=resources, original_case_never_fitted=True))
            save(args.out/'report.json', report)
            print('LOCKED_SOURCE_PREP', label, 'M', len(z['positions']), 'memory', resources['memory_passed'], flush=True)
        assert len(report['cases']) == 5 and report['cases'][0]['label'] == 'F3 Fifth First Mid'
        disk = sum(row['resources']['full_factor_disk_bytes'] for row in report['cases'])
        report.update(result='locked_source_five_prepared', all_resources_passed=all(
            row['resources']['memory_passed'] and row['resources']['disk_passed'] for row in report['cases']),
            retained_five_factor_bytes=disk, retained_five_disk_passed=shutil.disk_usage(args.out).free >= disk+2*1024**3,
            original96sources71inputs_unchanged=True, no_C_or_sustained_or_hearing_promotion=True)
        save(args.out/'report.json', report)
    except BaseException as error:
        report.update(result='failed', error=repr(error)); save(args.out/'report.json', report)
        raise


if __name__ == '__main__': main()
