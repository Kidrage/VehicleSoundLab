"""Archive native observation controls and isolated latent laws, preserving first attempts."""
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
    study=a.workspace/'references/analysis/phase_observation_native_v1'
    latent=a.workspace/'references/analysis/joint_latent_dynamics_v1'
    source,audit=load(study/'known2/report.json'),load(study/'known_audit2/report.json')
    review,proof=load(study/'review1/report.json'),load(study/'review_audit1/report.json')
    law=load(latent/'known2/report.json')
    assert audit['verification_passed'] and audit['producer_sha256']==sha(study/'known2/report.json')
    assert proof['verification_passed'] and proof['producer_sha256']==sha(study/'review1/report.json')
    assert proof['numeric_cells_independently_recomputed']==810 and len(audit['maximum_errors'])==4320
    assert len(source['cases'])==9 and len(law['cases'])==5 and law['verification_passed']
    assert load(latent/'known1/report.json')['result']=='failed'
    assert load(study/'known_audit1/report.json')['verification_passed']
    sources=set();inputs={}
    for result in (source,audit,review,law):
        for name,digest in result['sources'].items():assert sha(repo/name)==digest;sources.add(name)
    for name,path in source['inputs'].items():
        assert sha(name)==path
        # Original analytic fixtures and provenance reports only: no D factors.
        location=Path(name);assert location.drive.upper()=='E:'
        inputs['prior_inputs/'+location.relative_to(a.workspace).as_posix()]=location
    for location in latent.rglob('*'):
        if location.is_file():inputs['latent/'+location.relative_to(latent).as_posix()]=location
    assert sha(latent/'known2/known_laws.npz')==law['packet_sha256']
    sources.update(('tools/freeze_phase_observation_native_v1.py','research/观察窗与联合动态原型V1.md',
        'research/phase_observation_native_next_v1_plan.json','AGENTS.md','README.md',
        'handoff/研究续接.md','handoff/算法说明.md'))
    assert not list(study.rglob('*.wav')) and not list(study.rglob('*.bin'))
    assert not list(latent.rglob('*.wav')) and not list(latent.rglob('*.bin'))
    validation=dict(result='native_observation_and_known_joint_dynamics_archived',
        known_native_controls=9,independent_comparisons=4320,
        independent_native_max_error=audit['maximum_comparison_error'],
        independent_truth_definitions_for_every_variant=True,CSV_numeric_cells_checked=810,
        latent_known_laws=5,latent_max_error=law['maximum_error'],
        original_native_truth_scope_gap_preserved=True,original_latent_assertion_failure_preserved=True,
        current_native='known2/known_audit2',current_latent='known2',PNG_viewed=True,SVG_parsed=True,
        no_real_source_fit_training_audio_C_driver_room_default_or_hearing_change=True,
        no_vehicle_or_audible_cause_qualification=True,new_C1_source_eligible_for_statistics=False,
        protected_C_H=670,protected_voice_files=82,protected_F2_files=3,
        original_hearings_and_C_index_exact=True,no_actual_factor_files_copied=True,full_goal='ACTIVE')
    root=a.workspace/'baselines/phase_observation_native_v1'
    info=freeze(root,repo,sources,study,inputs,validation);verify(root)
    save(repo/'research/phase_observation_native_v1_summary.json',dict(validation,archive=str(root),**info))
    print('NATIVE_OBSERVATION_ARCHIVED',info,flush=True)


if __name__=='__main__':main()
