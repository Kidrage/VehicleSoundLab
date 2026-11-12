"""Bind every clock attempt and freeze an explicitly unaccepted real-source result."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--stage', choices=['publish', 'freeze'], required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

base = args.workspace/'references/analysis/multicarrier_clock_v1'
summary_path = repo/'research/multicarrier_clock_v1_summary.json'
final = base/'final1'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if args.stage == 'publish':
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    final.mkdir(exist_ok=False)
    result = dict(schema='vsl.multicarrier-clock-publication/1', result='running', reports={}, sources={})
    try:
        for name in [f'validate{i}' for i in range(1, 10)]+['E_source1']:
            path = base/name/'report.json'
            item = load(path)
            result['reports'][name] = dict(path=path.relative_to(args.workspace).as_posix(), sha256=sha(path), result=item['result'])
            for relative, digest in item['sources'].items():
                assert sha(path.parent/'exact_sources'/relative) == digest
                if name in ('validate9', 'E_source1'):
                    assert sha(repo/relative) == digest
        known = load(base/'validate9/report.json')
        real = load(base/'E_source1/report.json')
        assert known['result'] == 'passed' and len(known['cases']) == 18
        assert sum(not item['case'].get('negative', False) for item in known['cases']) == 15
        assert all(item['passed'] for item in known['cases'])
        assert real['result'] == 'source_phase_rejected' and real['track_status'] == 'measured_consensus'
        assert not real['model_exported'] and real['candidate'] is None
        assert not list(base.rglob('*.model'))
        with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 540
        hashes = {row['文件']: sha(repo/row['文件']) for row in rows}
        assert all(hashes[row['文件']] == row['SHA-256'] for row in rows)
        save(final/'C_files_sha256.json', hashes)
        prior = load(args.workspace/'references/analysis/E_low_state_v1/final1/voice_files_sha256.json')
        assert all(sha(repo/name) == digest for name, digest in prior.items())
        save(final/'voice_files_sha256.json', prior)
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules',
                        'experiments', 'voices', 'CMakeLists.txt'], cwd=repo, check=True, capture_output=True)
        names = ['low_drift', 'low_masking', 'low_phase_contamination', 'low_masking_2', 'rapid_corner']
        figure, axes = plt.subplots(2, 1, figsize=(12, 7), constrained_layout=True)
        positions = np.arange(len(names))
        for offset, stage in enumerate((2, 4, 7, 9)):
            data = load(base/f'validate{stage}/report.json')
            cases = {item['case']['id']: item for item in data['cases']}
            for axis, field, label in ((axes[0], 'root_relative_p95', 'p95 relative root error (%)'),
                                       (axes[1], 'maximum_oracle_band_power_error_db', 'Worst absolute band error (dB)')):
                values = [cases.get(name, {}).get(field, np.nan) for name in names]
                if axis is axes[0]:
                    values = [value*100 for value in values]
                axis.plot(positions, values, marker='o', label=f'validate{stage}')
                axis.set(ylabel=label, xticks=positions, xticklabels=names)
                axis.grid(alpha=.2)
        axes[0].axhline(1, color='red', linestyle='--', label='1% gate')
        axes[1].axhline(.5, color='red', linestyle='--', label='0.5 dB gate')
        axes[0].legend(ncol=5, fontsize=8)
        axes[1].legend(ncol=5, fontsize=8)
        figure.suptitle('Independent analytic controls only: pitch accuracy and high-order preservation differ\nMissing points are absent/rejected cases, not zero error; real E remains phase-rejected')
        figure.savefig(final/'known_control_comparison.png', dpi=140)
        plt.close(figure)
        positives = [item for item in known['cases'] if not item['case'].get('negative', False)]
        result.update(result='analytic_controls_pass_real_phase_rejected', positive_controls=15,
            negative_controls=3, maximum_root_relative_p95=max(item['root_relative_p95'] for item in positives),
            maximum_oracle_band_power_error_db=max(item['maximum_oracle_band_power_error_db'] for item in positives),
            maximum_oracle_complex_correlation_error=max(item['maximum_oracle_complex_correlation_error'] for item in positives),
            real_source_result=real['result'], real_source_case=real['source_case'],
            real_coarse_rows=len(load(base/'E_source1/coarse.json')['rows']),
            model_exported=False, real_C_render_executed=False, vehicle_timbre_accepted=False,
            runtime_changed=False, C_H=540, C_hashes_sha256=sha(final/'C_files_sha256.json'),
            voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            plot_sha256=sha(final/'known_control_comparison.png'),
            existing_Ctests_rerun=False, idle_acceleration_complete=False,
            original_generic_phase_gate='not_passed_unchanged', moving35='held_unchanged', date='2026-11-13')
        sources = [Path(__file__), repo/'tools/validate_multicarrier_clock_v1.py',
                   repo/'tools/fit_multicarrier_source_v1.py', repo/'research/multicarrier_clock_v1_plan.json',
                   repo/'research/多谱线声学坐标V1.md', repo/'research/E_stationary_dna_v1_plan.json']
        sources += list((repo/'tools/multicarrier_clock_v1').glob('*.py'))
        for source in sources:
            relative = source.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            result['sources'][relative.as_posix()] = sha(source)
        save(summary_path, result)
    except Exception as exc:
        result.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', result)
    print(json.dumps({key: result[key] for key in ('result', 'maximum_root_relative_p95',
          'maximum_oracle_band_power_error_db', 'maximum_oracle_complex_correlation_error', 'real_coarse_rows')}), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    summary = load(summary_path)
    assert summary['result'] == 'analytic_controls_pass_real_phase_rejected'
    assert sha(summary_path) == sha(final/'report.json')
    for item in summary['reports'].values():
        assert sha(args.workspace/item['path']) == item['sha256']
    for name, digest in summary['sources'].items():
        assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
        for name, digest in load(final/filename).items():
            assert sha(repo/name) == digest
    out = args.workspace/'baselines/multicarrier_clock_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(out.rglob('*')) if path.is_file()]
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=items,
        goal_complete=False, vehicle_timbre_accepted=False, real_profiles_exported=0,
        source_observations='E:/VehicleSoundLab/baselines/E_low_state_v1/manifest.json',
        source_observations_sha256=sha(args.workspace/'baselines/E_low_state_v1/manifest.json')))
    for item in items:
        assert sha(out/item['path']) == item['sha256']
    print(json.dumps(dict(result='frozen', commit=commit, files=len(items),
                         bytes=sum(item['bytes'] for item in items))), flush=True)
