"""Publish/freeze the same-spacing quintic candidate and boundedness audit."""
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
from drive_evidence_v1.sources import sha
base = args.workspace/'references/analysis/quintic_phase_v1'
final = base/'final1'
summary = repo/'research/quintic_phase_v1_summary.json'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


if args.stage == 'publish':
    final.mkdir(exist_ok=False)
    report = dict(schema='vsl.quintic-phase-publication/1', result='running', sources={}, reports={})
    try:
        reports = {}
        for name in ('dense1', 'audit1', 'observation1', 'observation2'):
            folder = base/name
            value = load(folder/'report.json')
            assert not value['real_audio_read'] and not value['real_source_permitted']
            reports[name] = value
            changed = set()
            for relative, digest in value['sources'].items():
                assert sha(folder/'exact_sources'/relative) == digest
                if sha(repo/relative) != digest:
                    changed.add(relative)
            expected = {'tools/diagnose_quintic_observation_v1.py'} if name == 'observation1' else set()
            assert changed == expected, (name, changed)
            report['reports'][name] = dict(path=(folder/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(folder/'report.json'), result=value['result'], changed_executed_sources=sorted(changed))
        candidate, audit = reports['dense1'], reports['audit1']
        assert candidate['result'] == 'dense_diagnostic_rejected' and not candidate['assessment']['qualified']
        assert candidate['controls']['passed'] and candidate['fit']['iterations'] == 20
        assert audit['result'] == 'reconstructed_quintic_candidate_migration_and_entire_trace'
        assert audit['entire_trace_exact'] and len(audit['trace']) == 20
        assert audit['qp_certified'] == 1 and audit['qp_uncertified'] == 19
        assert all(row['all_candidate_objective_and_decision_values_exact'] for row in audit['trace'])
        assert audit['shared_fit_refactor']['numerical_loop_AST_exact']
        assert audit['shared_fit_refactor']['observation_scaling_AST_exact']
        old, new = reports['observation1'], reports['observation2']
        assert old['result'] == new['result'] == 'diagnosed_raw_and_aperture_local_sensitivity_no_estimator_change'
        assert old['candidate_report_sha256'] == new['candidate_report_sha256'] == sha(base/'dense1/report.json')
        assert not new['may_initialize_estimator']
        # Observation2 adds explicit applicability/bounds limits without changing
        # any numerical quantity from the original diagnostic.
        for prior, current in zip(old['cases'], new['cases']):
            for key, value in prior.items():
                if key == 'components':
                    for prior_component, current_component in zip(value, current[key]):
                        assert all(current_component[k] == v for k, v in prior_component.items())
                else:
                    assert current[key] == value
            assert current['combined_original_phase_bound_exceeded']
            assert not current['quantitative_prediction_of_actual_bounded_estimator']
            assert all(c['original_phase_control_bound_exceeded'] for c in current['components'])
        previous = args.workspace/'references/analysis/joint_trust_v1/final1'
        for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
            hashes = load(previous/filename)
            assert all(sha(repo/name) == digest for name, digest in hashes.items())
            shutil.copy2(previous/filename, final/filename)
        assert len(load(final/'C_files_sha256.json')) == 540
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'src', 'modules', 'experiments', 'voices', 'CMakeLists.txt'],
            cwd=repo, capture_output=True, check=True)
        assert not list(base.rglob('*.model')) and not list(base.rglob('*.wav'))
        sources = {Path(__file__), repo/'AGENTS.md', repo/'handoff/算法说明.md', repo/'handoff/研究续接.md',
            repo/'handoff/开发留痕.md', repo/'research/怠速与加速完成度V1.md', repo/'research/五次共同相位V1.md'}
        for value in reports.values():
            sources.update(repo/name for name in value['sources'])
        for path in sources:
            relative = path.relative_to(repo)
            target = final/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            report['sources'][relative.as_posix()] = sha(path)
        shutil.copy2(args.workspace/'AGENTS.md', final/'data_workspace_AGENTS.md')
        shutil.copy2(previous/'qp_install_report.json', final/'qp_install_report.json')
        assert sha(base/'dense1/quintic_phase.png') == candidate['plot_sha256']
        shutil.copy2(base/'dense1/quintic_phase.png', final/'quintic_phase.png')
        report.update(result='same_spacing_quintic_actual_candidate_rejected',
            candidate={key: candidate['fit'][key] for key in ('initial_cost', 'final_cost', 'accepted_steps',
                'normalized_projection_residual', 'seconds')} | {'assessment': candidate['assessment']},
            original_cubic_assessment=candidate['original_assessment'], initialization=candidate['initialization'],
            independent_audit={key: audit[key] for key in ('shared_fit_refactor', 'observed_migration',
                'entire_trace_exact', 'accepted_steps', 'qp_certified', 'qp_uncertified')},
            local_observation_diagnosis=new['cases'],
            original17_rerun=False, full33_replaced=False, individual14kHz_demonstrated=False,
            real_source_permitted=False, source_audio_read=False, model_exported=False, runtime_changed=False,
            C_H=540, existing_Ctests_rerun=False, moving35='held_unchanged', new_media_downloaded=False,
            idle_acceleration_complete=False, vehicle_timbre_accepted=False,
            C_hashes_sha256=sha(final/'C_files_sha256.json'), voice_hashes_sha256=sha(final/'voice_files_sha256.json'),
            goal_turn_classification='progress_actual_quintic_estimator_full_trace_audit_and_noise_observation_diagnosis',
            previous_goal_turn_classification='verified_wait_specific_live_session90751_alongside_status_answer',
            next_step='Independently certify the actual bounded ill-conditioned QP subproblems before changing model/order/bandwidth; retain all17/full33/individual14kHz/original E gates and failed dense positive',
            limits=['Actual phase p95 exceeds original .0001 despite lower audio residual; no real idle/acceleration update',
                '19 of20 subproblems reach100000iterations; no subproblem/joint/global convergence claim',
                'Unbounded raw/aperture sensitivities exceed original phase bounds and are not quantitative actual error predictions',
                'Changing to raw waveform alone is not qualified; omitted lines are present and no raw estimator was run',
                'Shared fit source differs from the prior frozen stage only by audited model injection; prior executed sources remain frozen',
                'F1/F2/F3 and original A-low remain pending, no duplicate requests/downloads'])
        save(summary, report)
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        save(final/'report.json', report)
    print(json.dumps(dict(result=report['result'], real_models=0, trace=20, qp_uncertified=19)), flush=True)
else:
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    report = load(summary)
    assert report['result'] == 'same_spacing_quintic_actual_candidate_rejected'
    assert sha(summary) == sha(final/'report.json')
    for relative, digest in report['sources'].items():
        assert sha(repo/relative) == sha(final/'exact_sources'/relative) == digest
    for value in report['reports'].values():
        assert sha(args.workspace/value['path']) == value['sha256']
    out = args.workspace/'baselines/quintic_phase_v1'
    out.mkdir(exist_ok=False)
    shutil.copytree(base, out/'evidence')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), commit], cwd=repo, check=True)
    with zipfile.ZipFile(out/'source.zip') as archive:
        assert archive.testzip() is None
    items = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
        for p in sorted(out.rglob('*')) if p.is_file()]
    prior = args.workspace/'baselines/joint_trust_v1/manifest.json'
    save(out/'manifest.json', dict(schema='vsl.freeze/1', source_commit=commit, files=items,
        goal_complete=False, profiles_exported=0, source_evaluated=False, vehicle_timbre_accepted=False,
        prior_joint_manifest=prior.relative_to(args.workspace).as_posix(), prior_joint_manifest_sha256=sha(prior)))
    assert all(sha(out/item['path']) == item['sha256'] for item in items)
    print(json.dumps(dict(result='frozen', commit=commit, files=len(items), bytes=sum(item['bytes'] for item in items))), flush=True)
