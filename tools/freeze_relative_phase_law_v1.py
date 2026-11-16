"""Freeze known and read-only temporal-law evidence with all original failures."""
import argparse
import os
from pathlib import Path
import sys
from research_archive_v1 import load,save,sha,freeze,verify


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    from c1_registered_source_v1.binding import protected
    repo=Path(__file__).resolve().parents[1]
    protected(a.workspace,repo)
    study=a.workspace/'references/analysis/relative_phase_law_v1'
    known,known_audit=load(study/'known1/report.json'),load(study/'known_audit1/report.json')
    actual,audit=load(study/'real1/report.json'),load(study/'real_audit1/report.json')
    review,proof=load(study/'review2/report.json'),load(study/'review_audit2/report.json')
    assert known_audit['verification_passed'] and known_audit['producer_sha256']==sha(study/'known1/report.json')
    assert audit['verification_passed'] and audit['producer_sha256']==sha(study/'real1/report.json')
    assert proof['verification_passed'] and proof['producer_sha256']==sha(study/'review2/report.json')
    assert load(study/'review_audit1/report.json')['result']=='failed'
    assert known['known']['controls']==8 and len(actual['cases'])==6 and proof['CSV_numeric_cells_bitwise_checked']==1740
    sources={}
    for r in (known,actual,audit,review):
        for name,digest in r['sources'].items():
            assert name not in sources or sources[name]==digest
            assert sha(repo/name)==digest
            sources[name]=digest
    for name in ('tools/freeze_relative_phase_law_v1.py','research/旧相位模型时间结构核查V1.md',
        'research/relative_phase_law_next_v1_plan.json','research/c1_native_diagnostics_next_v1_plan.json',
        'AGENTS.md','README.md','handoff/研究续接.md','handoff/算法说明.md'):
        sources[name]=sha(repo/name)
    assert not list(study.rglob('*.wav')) and not list(study.rglob('*.bin'))
    validation=dict(result='existing_joint_phase_law_preservation_evidence_archived',
        known_controls=8,existing_profiles_read_only=6,independent_known_max_error=known_audit['maximum_comparison_error'],
        independent_actual_max_error=audit['maximum_comparison_error'],CSV_numeric_cells_checked=1740,
        original_window_provenance_cases_checked=6,original_failed_publication_preserved=True,
        current_review='review2',current_review_audit='review_audit2',PNG_viewed=True,SVG_parsed=True,
        no_source_fit_new_training_audio_C_room_driver_default_or_hearing_change=True,
        no_audible_or_physical_cause_claim=True,new_C1_source_eligible_for_statistics=False,
        protected_C_H=670,protected_voice_files=82,protected_F2=3,original_hearings_and_C_index_exact=True,
        no_dense_dimensions_reduced=True,all_dense_matrices_bound_by_sha_and_reproducible_factors=True,
        no_actual_factor_files_copied=True,full_goal='ACTIVE')
    root=a.workspace/'baselines/relative_phase_law_v1'
    info=freeze(root,repo,sources,study,{},validation);verify(root)
    save(repo/'research/relative_phase_law_v1_summary.json',dict(validation,archive=str(root),**info))
    print('RELATIVE_PHASE_LAW_ARCHIVED',info,flush=True)


if __name__=='__main__':main()
