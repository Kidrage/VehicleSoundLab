"""Freeze saved C1 diagnosis and both small known trials; bind D data, never copy it."""
import argparse
import os
from pathlib import Path
import sys
from research_archive_v1 import load,save,sha,freeze,verify


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    from c1_registered_source_v1.binding import protected
    repo=Path(__file__).resolve().parents[1];protected(a.workspace,repo)
    study=a.workspace/'references/analysis/c1_failed_band_v1'
    source,audit,review=[load(study/name/'report.json') for name in ('real1','real_audit1','review1')]
    assert audit['verification_passed'] and audit['producer_sha256']==sha(study/'real1/report.json')
    assert len(audit['comparisons'])==185 and audit['maximum_comparison_error']<2e-11
    assert not source['eligible_for_later_source_statistics'] and not source['original_fidelity_qualified']
    assert review['result']=='c1_failed_band_review_published' and review['CSV_numeric_cells_roundtrip_checked']==10355
    for name,digest in review['inputs'].items():assert sha(name)==digest
    for name,digest in review['files'].items():assert sha(study/'review1'/name)==digest
    sources=set();inputs={};external={}
    for report in (source,review):
        for name,digest in report['sources'].items():assert sha(repo/name)==digest;sources.add(name)
    for name,digest in source['inputs'].items():
        path=Path(name);assert sha(path)==digest
        if path.drive.upper()=='D:':
            assert 'factors' not in path.parts
            external[str(path)]=dict(sha256=digest,bytes=path.stat().st_size,copied=False)
        else:
            assert path.drive.upper()=='E:'
            inputs[path.relative_to(a.workspace).as_posix()]=path
    # Keep the executed known1 implementation as evidence, not current source.
    prototypes=a.workspace/'references/analysis/band_constrained_source_v1'
    known1,known2=[load(prototypes/name/'report.json') for name in ('known1','known2')]
    for name,report in (('known1',known1),('known2',known2)):
        assert report['verification_passed'] and len(report['cases'])==4
        assert not report['new_C1_source_eligible_for_statistics']
        assert sha(prototypes/name/'known.npz')==report['packet_sha256']
        for relative,digest in report['sources'].items():assert sha(prototypes/name/'exact_sources'/relative)==digest
        for path in sorted((prototypes/name).rglob('*')):
            if path.is_file():inputs[path.relative_to(a.workspace).as_posix()]=path
    assert len(known2['invalid_contract_rejections'])==11 and known2['zero_target_contract']['tiny_nonzero_rejected']
    assert known1['sources']['tools/band_constrained_source_v1/solver.py']!=known2['sources']['tools/band_constrained_source_v1/solver.py']
    for name,digest in known2['sources'].items():assert sha(repo/name)==digest;sources.add(name)
    # Frozen source closures remain untouched, including all registered failures.
    execution=load(next(Path(n) for n in external if Path(n).name=='execution_spec.json'))
    assert (len(execution['source_closure']),len(execution['input_closure']))==(206,144)
    for name,digest in execution['source_closure'].items():assert sha(repo/name)==digest
    registration=load(a.workspace/'references/analysis/c1_fit_registration_v1/registration1/report.json')['pair']['spec']
    assert len(registration['source_closure'])==196 and len(registration['toolchain']['native_files_sha256'])==131
    save(study/'external_hash_bindings.json',dict(D_inputs=external,no_D_files_or_factors_copied=True))
    sources.update(('tools/freeze_c1_failed_band_v1.py','research/C1失败频带与约束提取原型V1.md',
        'research/c1_failed_band_next_v1_plan.json','AGENTS.md','README.md','handoff/研究续接.md','handoff/算法说明.md'))
    assert not list(study.rglob('*.wav')) and not list(study.rglob('*.bin'))
    validation=dict(result='c1_failed_band_and_small_constrained_prototype_archived',
        independent_comparisons=185,independent_maximum_scaled_error=audit['maximum_comparison_error'],
        CSV_numeric_cells_roundtrip_checked=10355,PNG_viewed=True,SVG_parsed=True,
        original_highest_NRMSE=source['original_all_metrics']['target_supported_band_complex_NRMSE'][-1],
        nominal_same_objective_optimum_lower_bound=source['summary']['nominal_original_optimality']['exact_same_objective_optimum_NRMSE_lower_bound'],
        same_objective_bound_is_nominal_not_interval_arithmetic=True,
        known1_zero_target_scope_gap_preserved=True,known2_analytic_cases=3,known2_independent_SLSQP_cases=1,
        known2_invalid_inputs_rejected=11,known2_infeasible_case_rejected=True,
        constrained_large_scale_operator_resources_and_full_fidelity_pending=True,
        no_actual_fit_training_audio_C_driver_owned_take_room_default_or_hearing_change=True,
        no_physical_or_perceptual_cause_claim=True,new_C1_source_eligible_for_statistics=False,
        protected_C_H=670,protected_voice_files=82,protected_F2_files=3,
        original_hearings_and_C_index_exact=True,no_actual_D_files_or_factors_copied=True,full_goal='ACTIVE')
    root=a.workspace/'baselines/c1_failed_band_v1'
    info=freeze(root,repo,sources,study,inputs,validation);verify(root)
    save(repo/'research/c1_failed_band_v1_summary.json',dict(validation,archive=str(root),**info))
    print('C1_FAILED_BAND_ARCHIVED',info,flush=True)


if __name__=='__main__':main()
