"""Archive metadata-only paired claims and preserved synthetic failure fixtures."""
import argparse
from pathlib import Path
from research_archive_v1 import load, save, sha, freeze, append_index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    evidence = a.workspace/'references/analysis/c1_fit_registration_v1'
    reports, sources, bound = {}, set(), {}
    expected = dict(known1='c1_fit_registration_known_verified',
        registration1='c1_source_single_registration_reserved',
        registration_audit1='independent_c1_source_registration_verified')
    for stage, result in expected.items():
        r = load(evidence/stage/'report.json')
        assert r['result'] == result and r['verification_passed']
        reports[stage] = r
        for name, value in r['sources'].items():
            original = evidence/('registration1' if stage == 'registration_audit1' else stage)/'exact_sources'/name
            assert sha(repo/name) == sha(original) == value
            sources.add(name)
        for name, value in r.get('inputs', {}).items():
            assert sha(name) == value and Path(name).suffix != '.bin'
            bound[name] = value
    known, registration, audit = (reports[k] for k in expected)
    assert known['rejection_count'] == len(known['rejections']) == 18
    assert known['independent_success_pair_inspection'] and len(known['successes']) == 1
    assert audit['producer_sha256'] == sha(evidence/'registration1/report.json')
    assert (audit['authored_source_count'], audit['input_count'], audit['native_toolchain_file_count']) == (196, 137, 131)
    spec = registration['pair']['spec']
    assert spec['original_label'] == 'F3 Fifth First Late' and spec['state'] == 'reserved_only'
    assert audit['registration_sha256'] == registration['pair']['registration_sha256']
    for name in ('canonical_claim', 'storage_claim'):
        root = Path(spec[name])
        assert not (root/'launch_intent.json').exists() and not list(root.rglob('*.bin'))
        for filename in ('run_spec.json', 'pair_receipt.json'):
            path = root/filename
            bound[str(path)] = sha(path)
        assert sha(root/'run_spec.json') == audit['registration_sha256']
    for name, value in spec['toolchain']['native_files_sha256'].items():
        assert sha(name) == value
    previous = load(repo/'research/c1_declared_objective_v1_summary.json')
    for name, count in (('C_files_sha256.json', 670), ('voice_files_sha256.json', 82), ('F2_files_sha256.json', 3)):
        values = load(a.workspace/'baselines/c1_declared_objective_v1/evidence'/name)
        assert len(values) == count
        for relative, value in values.items():
            assert sha(repo/relative) == value
            sources.add(relative)
        save(evidence/name, values)
    assert sha(repo/'handoff/C文件索引.csv') == previous['protected_C_index_sha256']
    for name, value in previous['protected_hearings_sha256'].items():
        assert sha(repo/name) == value
    sources.update({'AGENTS.md', 'README.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv',
        'research/C1跨盘提取登记V1.md', 'research/c1_fit_registration_next_v1_plan.json',
        'research/locked_source_diagnostics_next_v1_plan.json', 'tools/freeze_c1_fit_registration_v1.py',
        'tools/verify_research_archive_independent_v1.py'})
    inputs = {}
    bases = (('workspace', a.workspace), ('repository', repo),
             ('storage', Path('D:/VehicleSoundLab-Work/source_fit_storage_v1')))
    for name, value in bound.items():
        path = Path(name)
        assert sha(path) == value
        prefix, base = next((prefix, base) for prefix, base in bases if path.is_relative_to(base))
        inputs[prefix+'/'+path.relative_to(base).as_posix()] = path
    validation = dict(result='c1_fit_registration_evidence_frozen',
        actual_completed_stages=list(expected), no_live_jobs=True,
        previous_goal_turn_classification='progress: complete declared input math and independent archive',
        this_goal_turn_classification='progress: actual known failure controls and paired source registration with independent provenance/resource audit',
        known_independent_successes=1, known_rejections=18,
        label=spec['original_label'], registration_sha256=audit['registration_sha256'],
        source_identity=spec['source_identity'], measurement_identity=spec['measurement_identity'],
        geometry=spec['geometry'], canonical_claim=spec['canonical_claim'], storage_claim=spec['storage_claim'],
        authored_source_count=196, input_count=137, native_identity_file_count=131,
        native_toolchain_payload_copied=False, runtime_identity=spec['toolchain'],
        original_resource_preflight=spec['resource_preflight'],
        no_real_fit_or_factor_allocation=True, no_launch_intent=True,
        original124sources101inputs151conditionalbindings_verified=True,
        original_captures_factors_failures_untouched=True, original_real_factor_files_copied=False,
        original_SciPy_preparation_audit_passed=False,
        source_fidelity_not_evaluated=True, eligible_for_later_source_statistics=False,
        protected_C_index_sha256=previous['protected_C_index_sha256'],
        protected_hearings_sha256=previous['protected_hearings_sha256'],
        no_C_model_defaults_driver_owned_takes_room_or_hearing_change=True,
        full_goal='ACTIVE: autonomous jointLR/naturalHF/multipleactualengines/allstates/V6fivebuses/independentphysical7.1.4',
        next_plan='research/c1_fit_registration_next_v1_plan.json',
        input_archive_locations={str(path):name for name,path in inputs.items()})
    root = a.workspace/'baselines/c1_fit_registration_v1'
    receipt = freeze(root, repo, sources, evidence, inputs, validation)
    save(repo/'research/c1_fit_registration_v1_summary.json', dict(validation, archive=str(root), **receipt))
    append_index(repo/'handoff/阶段索引.csv', ['c1_fit_registration_v1', 'baselines/c1_fit_registration_v1/manifest.json',
        str(receipt['file_count']), receipt['manifest_sha256'],
        'Known independent success+18rejections before ONE E/D FirstLate registration and independent identity/resource audit',
        'No launchintent/factors/realfit/sourcefidelity/statistics/runtime qualification; original failures retained',
        'research/C1跨盘提取登记V1.md | research/c1_fit_registration_v1_summary.json',
        'baselines/c1_fit_registration_v1/validation.json'])
    print('C1_REGISTRATION_FROZEN', receipt, flush=True)


if __name__ == '__main__':
    main()
