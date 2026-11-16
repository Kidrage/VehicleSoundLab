"""Freeze exact reduction evidence and diagnostic budgets without changing gates."""
import argparse
import csv
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
    study=a.workspace/'references/analysis/operator_roundoff_v1'
    source,audit,budget,review=[load(study/name/'report.json') for name in ('known1','audit1','budget1','review1')]
    assert audit['verification_passed'] and audit['producer_sha256']==sha(study/'known1/report.json')
    assert len(source['known']['cases'])==12 and len(source['known']['rejections'])==4
    assert len(source['cases'])==len(audit['cases'])==len(budget['cases'])==4
    values=sum(c['exact_output_values'] for c in audit['cases']);products=sum(c['exact_products'] for c in audit['cases'])
    assert (values,products)==(262284,20358792) and all(c['maximum_ULP_error']==0. for c in audit['cases'])
    assert budget['verification_passed'] and budget['whole_operator_qualification'] is False
    assert sum(v['other_path_exceeds_dense_arithmetic_only_budget'] for c in budget['cases'] for v in c['groups'])==17
    assert review['CSV_numeric_cells_roundtrip_checked']==216 and review['SVG_parsed']
    sources=set();inputs={}
    for report in (source,review,budget):
        for name,digest in report['sources'].items():assert sha(repo/name)==digest;sources.add(name)
        for name,digest in report['inputs'].items():
            path=Path(name);assert path.drive.upper()=='E:' and sha(path)==digest
            if not path.is_relative_to(study):inputs[path.relative_to(a.workspace).as_posix()]=path
    for name,digest in review['files'].items():assert sha(study/'review1'/name)==digest
    # The independent variant auditor reused already-frozen synthesis geometry;
    # bind its complete authored dependencies to that prior executed identity.
    prior=a.workspace/'references/analysis/constrained_source_operator_v1/known2'
    old=load(prior/'report.json');extra={}
    for name in ('tools/observer_complete_v1/synthesis.py','tools/observer_forward_v1/polyphase.py','tools/observer_forward_v1/operator.py'):
        digest=old['sources'][name];assert sha(repo/name)==sha(prior/'exact_sources'/name)==digest
        sources.add(name);extra[name]=digest
    save(study/'reused_audit_dependencies.json',dict(prior_report_sha256=sha(prior/'report.json'),sources=extra))
    rows=[dict(case=c['name'],**v) for c in budget['cases'] for v in c['groups']]
    table=study/'review1/arithmetic_budgets.csv'
    with table.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with table.open(encoding='utf-8',newline='') as stream:printed=list(csv.DictReader(stream))
    budget_cells=0
    for old,new in zip(rows,printed):
        for key,value in old.items():
            if isinstance(value,bool):assert new[key]==str(value)
            elif isinstance(value,str):assert new[key]==value
            else:assert float(new[key])==value;budget_cells+=1
    assert len(printed)==len(rows)==32
    sources.update(('tools/freeze_operator_roundoff_v1.py','research/弱频带舍入与精确乘加核查V1.md',
        'research/operator_roundoff_next_v1_plan.json','AGENTS.md','README.md','handoff/研究续接.md','handoff/算法说明.md'))
    assert not list(study.rglob('*.wav')) and not list(study.rglob('*.bin'))
    validation=dict(result='saved_known_roundoff_and_exact_reduction_evidence_archived',
        known_rational_controls=12,invalid_operand_rejections=4,saved_small_cases=4,
        exact_compensated_outputs_checked=values,exact_integer_products=products,maximum_ULP_error=0.,
        arithmetic_budget_groups=32,other_path_exceeds_arithmetic_only_budget_groups=17,
        CSV_numeric_cells_roundtrip_checked=216,additional_budget_CSV_numeric_cells_checked=budget_cells,
        PNG_viewed=True,SVG_parsed=True,original_19_failed_checks_and_2e_11_threshold_preserved=True,
        whole_operator_or_constrained_solver_qualification=False,new_C1_source_eligible_for_statistics=False,
        exact_rounded_matrix_reduction_not_exact_FFT_or_continuous_OSC=True,
        no_full_unchanged_case_rerun_actual_fit_audio_C_or_audible_cause_claim=True,
        protected_C_H=670,protected_voice_files=82,protected_F2_files=3,index_and_hearings_exact=True,
        no_D_or_factor_copies=True,full_goal='ACTIVE')
    root=a.workspace/'baselines/operator_roundoff_v1'
    info=freeze(root,repo,sources,study,inputs,validation);verify(root)
    save(repo/'research/operator_roundoff_v1_summary.json',dict(validation,archive=str(root),**info))
    print('EXACT_ROUNDOFF_ARCHIVED',info,flush=True)


if __name__=='__main__':main()
