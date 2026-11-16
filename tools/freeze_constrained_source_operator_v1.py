"""Publish and freeze a completed known assessment with all failed gates retained."""
import argparse
import csv
import os
from pathlib import Path
import sys
from research_archive_v1 import load,save,sha,freeze,verify


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from c1_registered_source_v1.binding import protected
    repo=Path(__file__).resolve().parents[1];protected(a.workspace,repo)
    study=a.workspace/'references/analysis/constrained_source_operator_v1'
    source=load(study/'known2/report.json');audit=load(study/'known_all_audit3/report.json')
    assert audit['result']=='complete_known_operator_all_checks_assessed' and not audit['verification_passed']
    assert audit['producer_sha256']==sha(study/'known2/report.json') and len(audit['failures'])==19
    assert len(audit['cases'])==len(source['cases'])==5
    assert all(v['unchanged_threshold']==2e-11 for v in audit['failures'])
    assert audit['cases'][-1]['elements_checked']==1393798 and audit['cases'][-1]['maximum_scaled_error']<2e-11
    for name in ('known_audit1','known_audit2','known_all_audit2'):
        assert load(study/name/'report.json')['result']=='failed'
    sources=set()
    for trial in ('known1','known2'):
        report=load(study/trial/'report.json')
        for name,digest in report['sources'].items():assert sha(study/trial/'exact_sources'/name)==digest
        for case in report['cases']:assert sha(study/trial/case['name']/'operators.npz')==case['packet_sha256']
    for name,digest in source['sources'].items():
        if name=='tools/audit_constrained_source_operator_v1.py':
            assert sha(repo/name)!=digest # explicit post-execution window-count correction
        else:assert sha(repo/name)==digest
        sources.add(name)
    assert sha(repo/'tools/audit_constrained_source_operator_all_v1.py')==audit['auditor_sha256']
    published=study/'review1';published.mkdir(exist_ok=False)
    rows=audit['failures'];case_rows=[dict(case=c['name'],elements=c['elements_checked'],
        maximum_scaled_error=c['maximum_scaled_error'],failed_checks=sum(v['case']==c['name'] for v in rows)) for c in audit['cases']]
    cells=0
    for name,values in (('failed_checks.csv',rows),('cases.csv',case_rows)):
        with (published/name).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader();writer.writerows(values)
        with (published/name).open(encoding='utf-8',newline='') as stream:printed=list(csv.DictReader(stream))
        assert len(printed)==len(values)
        for old,new in zip(values,printed):
            for key,value in old.items():
                if isinstance(value,str):assert new[key]==value
                else:assert float(new[key])==value;cells+=1
    save(published/'report.json',dict(result='failed_known_operator_assessment_published',
        audit_sha256=sha(study/'known_all_audit3/report.json'),CSV_numeric_cells_roundtrip_checked=cells,
        float64_explicit_mantissa_bits=np.finfo(np.float64).nmant,longdouble_explicit_mantissa_bits=np.finfo(np.longdouble).nmant,
        qualification_passed=False,no_failed_check_relabelled=True))
    sources.update(('tools/audit_constrained_source_operator_all_v1.py','tools/freeze_constrained_source_operator_v1.py',
        'research/完整声源算子与数值限制V1.md','research/constrained_source_operator_next_v1_plan.json',
        'AGENTS.md','README.md','handoff/算法说明.md','handoff/研究续接.md'))
    assert not list(study.rglob('*.wav')) and not list(study.rglob('*.bin'))
    validation=dict(result='complete_matrixfree_known_operator_assessment_archived',qualification_passed=False,
        known_cases=5,small_dense_cases=4,full_case_real_unknowns=84096,full_case_orders=288,full_case_nodes=73,
        full_case_elements_checked=1393798,all_cases_elements_checked=sum(c['elements_checked'] for c in audit['cases']),
        failed_checks_preserved=19,unchanged_check_threshold=2e-11,maximum_scaled_error=audit['maximum_scaled_error'],
        original_first_stop_failures_and_exhaustive_window_count_failure_preserved=True,
        current_first_stop_count_fix_not_relabelled_as_executed_pass=True,full_supported_windows=56,target_supported_windows=40,
        actual_float64_and_longdouble_explicit_mantissa_bits=52,CSV_numeric_cells_roundtrip_checked=cells,
        no_actual_fit_audio_C_native_rate_or_naturalness_qualification=True,
        constrained_solver_and_complete_resource_bound_pending=True,new_C1_source_eligible_for_statistics=False,
        protected_C_H=670,protected_voice_files=82,protected_F2_files=3,protected_index_and_hearings_exact=True,
        no_D_or_factor_copies=True,full_goal='ACTIVE')
    root=a.workspace/'baselines/constrained_source_operator_v1'
    info=freeze(root,repo,sources,study,{},validation);verify(root)
    save(repo/'research/constrained_source_operator_v1_summary.json',dict(validation,archive=str(root),**info))
    print('KNOWN_OPERATOR_ASSESSMENT_ARCHIVED',info,flush=True)


if __name__=='__main__':main()
