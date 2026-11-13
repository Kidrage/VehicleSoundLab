"""Publish and freeze the coordinate repair and original dense-control rejection."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--stage', choices=('publish', 'freeze', 'verify'), required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
root = args.workspace/'references/analysis/complex_radial_v1'; final = root/'final1'
summary = repo/'research/complex_radial_v1_summary.json'
frozen = args.workspace/'baselines/complex_radial_v1'


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_current(r):
    for file, digest in r['sources'].items():
        assert sha(repo/file) == sha(final/'exact_sources'/file) == digest
    for item in r['reports'].values():
        assert sha(args.workspace/item['path']) == item['sha256']
    for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/file) == digest for file, digest in load(final/name).items())
    assert len(load(final/'C_files_sha256.json')) == 540
    assert sha(repo/'references/segments_v1.json') == sha(args.workspace/'references/segments_v1.json') == r['catalogue_sha256']
    assert sha(args.workspace/'AGENTS.md') == sha(final/'data_workspace_AGENTS.md') == r['data_memory_sha256']
    for item in r['prior_manifests'].values():
        assert sha(args.workspace/item['path']) == item['sha256']
    subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
        cwd=repo, capture_output=True, check=True)


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    r = dict(schema='vsl.complex-radial-final/1', result='running', sources={}, reports={})
    try:
        folders = {n: root/n for n in ('controls1', 'fit1', 'audit1', 'review1')}
        values = {n: load(folder/'report.json') for n, folder in folders.items()}
        controls, actual, audit, review = (values[n] for n in ('controls1', 'fit1', 'audit1', 'review1'))
        assert controls['result'] == 'radial_loss_QP_and_observed_derivative_controls_passed'
        assert controls['controls']['passed']
        assert actual['result'] == 'dense_radial_rejected' and not actual['assessment']['qualified']
        assert actual['qp_certified'] == audit['qp_certified'] == 20
        assert actual['fit']['iterations'] == 20 and actual['fit']['accepted_steps'] == 18
        assert audit['result'] == 'radial_geometry_all_QP_certificates_and_entire_fit_trace_reconstructed'
        assert audit['entire_trace_and_final_assessment_exact']
        assert audit['fit_report_sha256'] == sha(folders['fit1']/'report.json')
        assert actual['controls_report_sha256'] == audit['controls_report_sha256'] == sha(folders['controls1']/'report.json')
        sources = {Path(__file__), repo/'AGENTS.md', repo/'research/复数径向损失V1.md',
            repo/'research/complex_radial_v1_plan.json', repo/'handoff/研究续接.md', repo/'handoff/算法说明.md',
            repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md'}
        for name, value in values.items():
            assert not value['real_audio_read'] and not value['model_exported'] and not value['runtime_changed']
            r['reports'][name] = dict(path=(folders[name]/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(folders[name]/'report.json'), result=value['result'])
            for file, digest in value['sources'].items():
                assert sha(repo/file) == sha(folders[name]/'exact_sources'/file) == digest
                sources.add(repo/file)
        for name, digest in review['reports_sha256'].items():
            assert sha(root/name/'report.json') == digest
        figure = folders['review1']/'complex_radial_comparison.png'
        assert sha(figure) == review['plot_sha256']
        for source in sources:
            relative = source.relative_to(repo); target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
            r['sources'][relative.as_posix()] = sha(source)
        previous = args.workspace/'references/analysis/F2_variation_projection_v1/final1'
        for name in ('C_files_sha256.json', 'voice_files_sha256.json'):
            shutil.copy2(previous/name, final/name)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        shutil.copy2(figure, final/figure.name)
        parents = {name: dict(path='baselines/'+name+'/manifest.json',
            sha256=sha(args.workspace/'baselines'/name/'manifest.json'))
            for name in ('correlated_observation_v1', 'F2_variation_projection_v1')}
        geometry_error = max(max(row['independent_geometry_errors'].values()) for row in audit['trace'])
        r.update(result='rotation_invariant_objective_repaired_original_dense36_phase_STILL_REJECTED',
            real_audio_read=False, prior_manifests=parents,
            catalogue_sha256=sha(repo/'references/segments_v1.json'), data_memory_sha256=sha(final/'data_workspace_AGENTS.md'),
            controls=controls['controls'], observed_checks={k: v for k, v in controls.items() if k.startswith('observed_')},
            fit_summary={k: actual['fit'][k] for k in ('iterations', 'accepted_steps', 'seconds', 'initial_cost',
                'final_cost', 'normalized_projection_residual', 'truth_used', 'heldout_used')},
            qp_certified=20, independent_geometry_max_relative_error=geometry_error,
            independent_scale_relative_error=audit['independent_scale_relative_error'],
            phase_p95=audit['phase_p95'], assessment=actual['assessment'], cross_objective_costs=audit['cross_objective_costs'],
            C_H=540, C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            plot_sha256=sha(figure), figures_visually_checked=True, existing55CTests_rerun=False,
            model_exported=False, runtime_changed=False, high_frequency_recovered=False,
            RPM_inferred=False, vehicle_timbre_accepted=False, idle_acceleration_complete=False,
            real_shared_phase_DNA_permitted=False, full_qualification=False, goal_complete=False,
            moving35='held_unchanged', original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_fixed2_3_5_geometry_all12groups24projections72predictions_audited_frozen_pushed',
            current_goal_turn='progress_radial_coordinate_repair_controls_original20step_failure_and_independent_full_trace_audit',
            next_step='Observed-only band-out interference/noise-geometry qualification with independent controls. '
                'Original failed36/all17/full33/individual14k/originalE remain required. '
                'No truth initialization, heldout fitting, blind bound/strength/degree/window/iteration sweeps; F2g(T) is not a synthesis clock.',
            limits=actual['limits']+audit['limits']+review['limits'])
        verify_current(r); save(summary, r)
    except Exception as exc:
        r.update(result='failed', error=repr(exc)); raise
    finally:
        save(final/'report.json', r)
    print(json.dumps(dict(result=r['result'], phase_p95=r['phase_p95'], qp_certified=r['qp_certified'])), flush=True)
elif args.stage == 'freeze':
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    r = load(summary); verify_current(r); assert sha(summary) == sha(final/'report.json')
    frozen.mkdir(exist_ok=False); shutil.copytree(root, frozen/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(frozen/'source.zip'), commit], cwd=repo, check=True)
    files = [dict(path=x.relative_to(frozen).as_posix(), bytes=x.stat().st_size, sha256=sha(x))
        for x in sorted(frozen.rglob('*')) if x.is_file()]
    save(frozen/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=files,
        prior_manifests=r['prior_manifests'], real_audio_read=False, profiles_exported=0,
        original_dense_control_qualified=False, vehicle_timbre_accepted=False, goal_complete=False))
    print(json.dumps(dict(result='frozen', files=len(files), bytes=sum(x['bytes'] for x in files),
        commit=commit, manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
else:
    r = load(summary); verify_current(r); m = load(frozen/'manifest.json')
    assert sha(summary) == sha(final/'report.json') == sha(frozen/'evidence/final1/report.json')
    for item in m['files']:
        assert sha(frozen/item['path']) == item['sha256'] and (frozen/item['path']).stat().st_size == item['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as archive:
        assert archive.testzip() is None
        for file, digest in r['sources'].items():
            assert hashlib.sha256(archive.read(file)).hexdigest() == digest
    for item in m['prior_manifests'].values():
        path = args.workspace/item['path']; assert sha(path) == item['sha256']
        for row in load(path)['files']:
            assert sha(path.parent/row['path']) == row['sha256']
    print(json.dumps(dict(result='all_frozen_payloads_sources_parents_C_voices_verified',
        files=len(m['files']), manifest_sha256=sha(frozen/'manifest.json'))), flush=True)
