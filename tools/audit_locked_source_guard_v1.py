"""Separate new-method complete audit; preserve the original terminal failure."""
import argparse
import copy
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'measurement-check', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--known-check', action='store_true')
    parser.add_argument('--guard-known', type=Path)
    args = parser.parse_args()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from locked_source_guard_v1.complete import verify
    repo = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', inputs={}, sources={}, cases=[])

    def read(path):
        report['inputs'][str(path)] = sha(path)
        return load(path)

    try:
        checked = read(args.measurement_check/'report.json')
        assert checked['result'] == 'independent_locked_saved_wave_measurement_controls_verified' and checked['all_qualified']
        for name, expected in checked['sources'].items():
            assert sha(repo/name) == sha(args.measurement_check/'exact_sources'/name) == expected
        if args.known_check:
            binding = args.study/'report.json'
            source = read(binding)
            assert source['result'] == 'locked_source_fit_known_measured' and source['all_qualified']
            original = read(args.workspace/'references/analysis/locked_source_fit_v1/known_audit1/report.json')
            assert original['result'] == 'independent_locked_source_known_verified' and original['all_qualified']
            assert original['producer_sha256'] == sha(binding)
            directories = [args.study/row['label'] for row in source['cases'] if row['label'] != 'both_zero']
            assert len(directories) == 3
        else:
            assert args.guard_known is not None
            original = read(args.guard_known/'report.json')
            assert original['result'] == 'independent_locked_source_guard_known_verified' and original['all_qualified']
            assert len(original['cases']) == 3 and len(original['invalid_rejections']) == 5
            binding = args.study.parent/'run_spec.json'
            source = read(binding)
            assert source['schema'] == 'vsl.locked_source_real_spec/1' and source['only_one_finite_case']
            assert source['declared_cases'] == [args.study.name] and args.study.name != 'F3 Fifth First Early'
            failed = read(args.study.parent/(args.study.name+'_audit')/'report.json')
            assert failed['result'] == 'failed'
            terminal = read(args.study.parent/'report.json')
            assert terminal['result'] == 'failed'
            context = read(args.workspace/'references/analysis/locked_source_metric_v1/diagnosis1/context_verification.json')
            for path, expected in context['inputs'].items():
                assert sha(path) == expected
            assert context['dependent_stages_executed'] == 0
            report['original_terminal_and_audit_failures_retained'] = True
            directories = [args.study]
        names = set(source['sources']) | {'tools/audit_locked_source_guard_v1.py',
            'tools/check_locked_source_measurement_v1.py', 'tools/research_archive_v1.py'}
        names.update(path.relative_to(repo).as_posix() for path in (repo/'tools/locked_source_guard_v1').glob('*.py'))
        for name in sorted(names):
            dest = args.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            report['sources'][name] = sha(dest)
            if name in source['sources']:
                assert report['sources'][name] == source['sources'][name]
        for path, expected in source.get('inputs', {}).items():
            assert sha(path) == expected
            report['inputs'][path] = expected
        if not args.known_check:
            for name, expected in original['sources'].items():
                assert sha(repo/name) == sha(args.guard_known/'exact_sources'/name) == expected
        for directory in directories:
            if args.known_check:
                bound = next(value for value in source['cases'] if value['label'] == directory.name)
                assert sha(directory/'report.json') == bound['report_sha256']
                assert sha(directory/'capture.npz') == bound['capture_sha256']
                for path in (directory/'report.json', directory/'capture.npz'):
                    assert original['inputs'][str(path)] == sha(path)
            row = verify(directory)
            if args.known_check:
                assert row['all_qualified']
            report['inputs'][str(directory/'report.json')] = sha(directory/'report.json')
            report['inputs'][str(directory/'capture.npz')] = sha(directory/'capture.npz')
            report['cases'].append(dict(label=directory.name, **row))
            save(args.out/'report.json', report)
            print('SAVED_WAVE_COMPLETE_AUDIT', directory.name, row['solver_qualified'], row['fidelity_qualified'], flush=True)
        if args.known_check:
            directory = directories[0]
            original_info = load(directory/'report.json')
            with np.load(directory/'capture.npz') as saved:
                original_arrays = {name: saved[name] for name in saved.files}
            rejected = []
            changes = (
                ('wave', 'all_order_scalar_waveform'), ('packed', 'independent_LR_interleave'),
                ('metric', 'declared_target_supported_band_complex_NRMSE'),
                ('history', 'node_update_0'), ('fidelity', 'fidelity_flag'))
            for label, expected_error in changes:
                target = args.out/'invalid'/label
                target.mkdir(parents=True)
                arrays = {name: value.copy() for name, value in original_arrays.items()}
                info = copy.deepcopy(original_info)
                if label == 'wave': arrays['wave'][4000, 0] += 1e-5
                elif label == 'packed': arrays['q'][0, 0] += .01
                elif label == 'metric': info['metrics']['target_supported_band_complex_NRMSE'][-1] += .1
                elif label == 'history': arrays['history_z'][1, 0, 0] += .01
                elif label == 'fidelity': info['fidelity_qualified'] = not info['fidelity_qualified']
                np.savez_compressed(target/'capture.npz', **arrays)
                info['capture_sha256'] = sha(target/'capture.npz')
                save(target/'report.json', info)
                try:
                    verify(target)
                except AssertionError as error:
                    assert expected_error in str(error), (label, str(error))
                    rejected.append(dict(label=label, error=str(error)))
                else:
                    raise AssertionError('Corrupted known capture passed: '+label)
            report['invalid_rejections'] = rejected
        for name, expected in report['sources'].items():
            assert sha(repo/name) == sha(args.out/'exact_sources'/name) == expected
        if args.known_check:
            report.update(result='independent_locked_source_guard_known_verified',
                verification_passed=True, all_qualified=all(row['all_qualified'] for row in report['cases']))
        else:
            report.update(result='independent_locked_source_real_verified', verification_passed=True,
                all_qualified=report['cases'][0]['all_qualified'], case=report['cases'][0])
        report.update(original_cross_operator_failures_not_relabelled=True,
            verification_scope='complete equations, independent scalar wave, saved wave declared metrics, all histories and resources',
            all_original_gates_unchanged=True, no_fit_C_sustained_or_hearing_promotion=True)
        save(args.out/'report.json', report)
    except BaseException as error:
        report.update(result='failed', error=repr(error))
        save(args.out/'report.json', report)
        raise


if __name__ == '__main__':
    main()
