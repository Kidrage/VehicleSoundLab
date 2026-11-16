"""Freeze read-only six-profile source support; no actual D-factor copies."""
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
    study=a.workspace/'references/analysis/phase_source_support_v1'
    source,audit,review=[load(study/name/'report.json') for name in ('real1','real_audit1','review1')]
    assert audit['verification_passed'] and audit['producer_sha256']==sha(study/'real1/report.json')
    assert len(source['known'])==4 and len(source['cases'])==len(audit['cases'])==6
    assert all(v['pairs_checked']==66 and v['harmonics_checked']==288 for v in audit['cases'])
    assert review['result']=='saved_phase_source_support_review_published' and review['CSV_numeric_cells_roundtrip_checked']==13680
    assert review['inputs'][str(study/'real1/report.json')]==sha(study/'real1/report.json')
    assert review['inputs'][str(study/'real_audit1/report.json')]==sha(study/'real_audit1/report.json')
    sources=set();inputs={}
    for r in (source,review):
        for name,digest in r['sources'].items():assert sha(repo/name)==digest;sources.add(name)
    for name,digest in source['inputs'].items():
        location=Path(name);assert location.drive.upper()=='E:' and sha(location)==digest
        inputs[location.relative_to(a.workspace).as_posix()]=location
    for name,digest in review['files'].items():assert sha(study/'review1'/name)==digest
    sources.update(('tools/freeze_phase_source_support_v1.py','research/联合方向的原始声源支持V1.md',
        'research/phase_source_support_next_v1_plan.json','AGENTS.md','README.md','handoff/研究续接.md','handoff/算法说明.md'))
    assert not list(study.rglob('*.wav')) and not list(study.rglob('*.bin'))
    validation=dict(result='six_saved_feature_direction_source_support_archived',known_controls=4,
        read_only_contexts=6,PC_pairs_checked=396,harmonic_traces_checked=1728,
        independent_maximum_scaled_error=audit['maximum_comparison_error'],
        CSV_numeric_cells_roundtrip_checked=13680,PNG_viewed=True,SVG_parsed=True,
        no_source_fit_training_audio_C_driver_owned_take_room_default_or_hearing_change=True,
        no_physical_or_perceptual_cause_claim=True,new_C1_source_eligible_for_statistics=False,
        protected_C_H=670,protected_voice_files=82,protected_F2_files=3,
        original_hearings_and_C_index_exact=True,no_actual_factor_files_copied=True,
        independent_temporal_law_not_identified=True,full_goal='ACTIVE')
    root=a.workspace/'baselines/phase_source_support_v1'
    info=freeze(root,repo,sources,study,inputs,validation);verify(root)
    save(repo/'research/phase_source_support_v1_summary.json',dict(validation,archive=str(root),**info))
    print('SOURCE_SUPPORT_ARCHIVED',info,flush=True)


if __name__=='__main__':main()
