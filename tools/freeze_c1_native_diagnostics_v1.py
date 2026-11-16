"""Archive terminal known diagnostics and a live observation, never live factors."""
import argparse
import os
from pathlib import Path
import sys
from research_archive_v1 import load, save, sha, freeze, verify


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    from c1_registered_source_v1.binding import execution
    repo = Path(__file__).resolve().parents[1]
    study = a.workspace/'references/analysis/c1_native_diagnostics_v1'
    known, audit = load(study/'known2/report.json'), load(study/'known_declared_audit2/report.json')
    assert known['all_known_qualified'] and audit['verification_passed'] and audit['all_known_qualified']
    assert audit['producer_sha256'] == sha(study/'known2/report.json')
    assert len(audit['retained_original_fsum_centering_failures']) == 20
    assert load(study/'known_audit1/report.json')['result'] == 'failed'
    contract = load(study/'contract1/report.json')
    assert contract['verification_passed'] and contract['rejected'] == 6
    pair, spec = execution(a.workspace, repo)
    assert len(spec['source_closure']) == 206 and len(spec['input_closure']) == 144
    assert not list(study.rglob('*.bin'))
    sources = dict(known['sources'])
    for report in (audit, contract):
        for name, digest in report['sources'].items():
            assert name not in sources or sources[name] == digest
            sources[name] = digest
    for name in ('tools/run_c1_native_followthrough_v1.ps1', 'tools/freeze_c1_native_diagnostics_v1.py',
        'research/C1原采样率保真核查V1.md', 'research/c1_native_diagnostics_next_v1_plan.json',
        'AGENTS.md', 'README.md', 'handoff/研究续接.md'):
        sources[name] = sha(repo/name)
    for name, digest in sources.items():
        assert sha(repo/name) == digest
    observation = load(study/'live_observation1.json')
    validation = dict(result='c1_declared_native_known_qualified_and_live_followthrough_archived',
        known_cases=4, controls=5, contract_success=1, contract_rejections=6,
        original_fsum_centering_failed_fields=20, original_failed_audit_preserved=True,
        original_execution_sources=206, original_execution_inputs=144,
        protected_C_H=670, protected_voices=82, protected_F2=3,
        original_execution_spec_sha256=sha(Path(pair['spec']['canonical_claim'])/'execution_spec.json'),
        live_observation=observation, no_live_factors_or_real_capture_copied=True,
        source_fidelity_not_evaluated=True, eligible_for_later_source_statistics=False,
        no_C_default_driver_owned_takes_room_or_hearing_change=True)
    baseline = a.workspace/'baselines/c1_native_diagnostics_known_v1'
    inputs = {'source_execution_spec.json':Path(pair['spec']['canonical_claim'])/'execution_spec.json',
        'source_registration.json':Path(pair['spec']['canonical_claim'])/'run_spec.json',
        'executed_followthrough.ps1':a.workspace/'references/analysis/c1_native_followthrough_v1/run1/executed_followthrough.ps1'}
    info = freeze(baseline, repo, sources, study, inputs, validation)
    verify(baseline)
    summary = dict(validation, archive=str(baseline), **info)
    save(repo/'research/c1_native_diagnostics_known_v1_summary.json', summary)
    print('C1_NATIVE_ARCHIVED', info, flush=True)


if __name__ == '__main__':
    main()
