"""Publish and freeze diagnosis, preserving both initial and corrected meters."""
import argparse
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
import numpy as np
from drive_evidence_v1.sources import sha

base = args.workspace/'references/analysis/period_structure_v1'
final = base/'final1'
summary_path = repo/'research/period_structure_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    result = dict(schema='vsl.period-structure-publication/1', result='running', reports={}, sources={})
    try:
        for name in ('observe1', 'observe2', 'leakage1', 'leakage2'):
            path = base/name/'report.json'
            report = load(path)
            assert report['result'] in ('observed_no_new_clock_or_model', 'analytic_short_projection_leakage_confirmed')
            result['reports'][name] = dict(path=path.relative_to(args.workspace).as_posix(), sha256=sha(path), result=report['result'])
            for relative, digest in report['sources'].items():
                assert sha(path.parent/'exact_sources'/relative) == digest
                if name in ('observe2', 'leakage2'):
                    assert sha(repo/relative) == digest
        observed = load(base/'observe2/report.json')
        leakage = load(base/'leakage2/report.json')
        assert observed['result'] == 'observed_no_new_clock_or_model'
        assert leakage['result'] == 'analytic_short_projection_leakage_confirmed' and not leakage['source_audio_read']
        for filename, field in [('prior_report.json', 'prior_report_sha256'), ('saved_coarse.json', 'saved_coarse_sha256')]:
            assert sha(base/'observe2'/filename) == observed[field]
        clock_path = args.workspace/'references/analysis/multicarrier_clock_v1/E_source1'
        assert sha(clock_path/'report.json') == observed['prior_report_sha256']
        assert sha(clock_path/'coarse.json') == observed['saved_coarse_sha256']
        assert sha(args.workspace/leakage['warp_null']['coordinate_file']) == leakage['warp_null']['coordinate_file_sha256']
        with np.load(base/'observe1/initial_coordinates_and_stereo.npz') as first, np.load(base/'observe2/initial_coordinates_and_stereo.npz') as second:
            assert first.files == second.files
            assert all(np.array_equal(first[name], second[name]) for name in first.files)
        assert sum(row['passed'] is True for row in observed['fixtures']) == 5
        assert next(row for row in observed['fixtures'] if row['id']=='noise_only')['passed'] is None
        hashes = load(base/'observe2/C_files_sha256.json')
        voices = load(base/'observe2/voice_files_sha256.json')
        assert len(hashes) == 540 and all(sha(repo/name) == digest for name, digest in hashes.items())
        assert all(sha(repo/name) == digest for name, digest in voices.items())
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
            cwd=repo, check=True, capture_output=True)
        save(final/'C_files_sha256.json', hashes)
        save(final/'voice_files_sha256.json', voices)
        occupancy = {}
        for view in ('raw_spectrum', 'coarse_coordinate_spectrum'):
            occupancy[view] = {}
            for part in ('full', 'first_half', 'last_half'):
                occupancy[view][part] = [dict(integer_peaks=channel['lattice']['integer_peaks'],
                    fractional_peaks=channel['lattice']['fractional_peaks'],
                    fifth_grid=channel['lattice']['hypotheses']['5']) for channel in observed[view][part]['channels']]
        sources = [Path(__file__), repo/'research/低转周期结构与带宽V1.md', repo/'research/period_structure_v1_plan.json',
            repo/'research/period_structure_v1_leakage_plan.json', repo/'tools/observe_period_structure_v1.py',
            repo/'tools/diagnose_period_leakage_v1.py', repo/'handoff/算法说明.md', repo/'handoff/研究续接.md',
            repo/'research/怠速与加速完成度V1.md', repo/'AGENTS.md']+list((repo/'tools/period_structure_v1').glob('*.py'))
        for source in sources:
            relative = source.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            result['sources'][relative.as_posix()] = sha(source)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        result.update(result='fractional_structure_and_short_projection_leakage_observed', date='2026-11-13',
            source_seconds=[5.2, 7.8], existing_coarse_root_hz=observed['display_root_hz'],
            frequency_meter_positive_checks=5, noise_meter='observed_only_not_period_qualified',
            maximum_analytic_peak_order_error=max(max(row['maximum_expected_peak_order_error_LR'])
                for row in observed['fixtures'] if row.get('maximum_expected_peak_order_error_LR')),
            AM_long_period_formula_difference=observed['AM_long_period_sample_difference'],
            selected_fractional_peak_occupancy=occupancy,
            analytic_projection_comparison=[dict(id=row['id'], windows={key:item['maximum_pair_drift_cycles']
                for key,item in row['windows'].items()}) for row in leakage['cases']],
            conditional_bandwidth_budget=observed['conditional_bandwidth_budget'],
            prior_real_phase_gate='source_phase_rejected_unchanged',
            model_exported=False, real_C_render_executed=False, engine_period_identified=False,
            vehicle_timbre_accepted=False, runtime_changed=False, existing_Ctests_rerun=False,
            C_H=540, moving35='held_unchanged', idle_acceleration_complete=False, new_media_downloaded=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            plot=dict(path=(base/'observe2/period_structure.png').relative_to(args.workspace).as_posix(),
                sha256=sha(base/'observe2/period_structure.png'), visually_inspected=True),
            previous_goal_turn='no_progress_status_only_revalidated',
            this_turn='progress_new_source_structure_leakage_controls_and_bandwidth_evidence',
            next_step='Independently qualify fractional-line-resolving common phase and high-frequency/stereo retention; then one declared source case plus independent carriers and contiguous-half timbre holdouts',
            limits=['Fifth-grid occupancy is selected-peak power, not total power or a period probability',
                'AM, longer cycles, source mixture and transfer remain ambiguous; no root/5 or physical RPM asserted',
                'Known analytic leakage does not establish the sole cause of real-source rejection',
                'Wider/sparse harmonic representation and bandwidth must be designed before any lower-root model export',
                'F1/F2/F3 and original A low listening remain pending; no duplicate question'],
            attempts=dict(observe1='Initial window-energy scale retained; no model accepted',
                observe2='Coherent-line normalization correction; initial stereo/coordinates exactly equal',
                leakage1='Initial analytic projection counterexamples', leakage2='Adds saved-coordinate constant-sine null and preserves identical analytic results'))
        save(summary_path, result)
    except Exception as exc:
        result.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', result)
    print(json.dumps(dict(result=result['result'], checks=5, source_models=0, unchanged_C_H=540)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    result = load(summary_path)
    assert result['result'] == 'fractional_structure_and_short_projection_leakage_observed'
    assert sha(summary_path) == sha(final/'report.json')
    for item in result['reports'].values():
        assert sha(args.workspace/item['path']) == item['sha256']
    for name, digest in result['sources'].items():
        assert sha(repo/name) == sha(final/'exact_sources'/name) == digest
    for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
        for name, digest in load(final/filename).items():
            assert sha(repo/name) == digest
    out = args.workspace/'baselines/period_structure_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items = [dict(path=path.relative_to(out).as_posix(), bytes=path.stat().st_size, sha256=sha(path))
        for path in sorted(out.rglob('*')) if path.is_file()]
    prior_manifest = args.workspace/'baselines/multicarrier_clock_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=items,
        goal_complete=False, vehicle_timbre_accepted=False, profiles_exported=0,
        source_coordinate_freeze=prior_manifest.relative_to(args.workspace).as_posix(), source_coordinate_manifest_sha256=sha(prior_manifest)))
    for item in items:
        assert sha(out/item['path']) == item['sha256']
    print(json.dumps(dict(result='frozen', commit=commit, files=len(items), bytes=sum(item['bytes'] for item in items))), flush=True)
