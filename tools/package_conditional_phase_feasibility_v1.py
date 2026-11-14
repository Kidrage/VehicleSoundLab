"""Freeze conditional-phase feasibility evidence without changing runtime DSP."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true')
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    evidence=a.workspace/'references/analysis/conditional_phase_feasibility_v1'
    root=a.workspace/'baselines/conditional_phase_feasibility_v1'
    if a.verify:
        manifest=verify(root);print(dict(result='archive_verified',files=manifest['file_count'],bytes=manifest['bytes']));return
    parent=a.workspace/'baselines/stereo_phase_budget_v1';parent_summary=load(repo/'research/stereo_phase_budget_v1_summary.json')
    assert sha(parent/'manifest.json')==parent_summary['manifest_sha256']
    protected={}
    for name,count in [('C_files_sha256.json',670),('voice_files_sha256.json',82),('F2_files_sha256.json',3)]:
        hashes=load(parent/'evidence'/name);assert len(hashes)==count
        assert all(sha(repo/n)==h for n,h in hashes.items());save(evidence/name,hashes);protected[name]=hashes
    names=set()
    for args in [['ls-files','-z'],['ls-files','--others','--exclude-standard','-z']]:
        names.update(subprocess.check_output(['git']+args,cwd=repo).decode('utf-8').split('\0'))
    names.discard('')
    assert {n for n in names if Path(n).suffix in ('.c','.h')}==set(protected['C_files_sha256.json'])
    index=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='')))
    assert len(index)==671 and all(r[4]==protected['C_files_sha256.json'][r[0]] for r in index[1:])
    entries={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    hearing=repo/'research/relative_phase_v1_listening.json'
    assert sha(hearing)==entries['source/research/relative_phase_v1_listening.json']
    studies={name:load(evidence/name/'report.json') for name in ['known1','known_audit1','real1','real_audit1','real_audit2','review1','review2']}
    assert studies['known1']['result']=='conditional_phase_known_controls_ready'
    assert len(studies['known1']['cases'])==8
    assert studies['real1']['result']=='six_source_conditional_phase_feasibility_ready'
    assert len(studies['real1']['cases'])==6 and all(len(r['harmonics'])==288 for r in studies['real1']['cases'])
    for name in ('known1','real1'):
        for n,h in studies[name]['sources'].items():assert sha(repo/n)==sha(evidence/name/'exact_sources'/n)==h
        for n,h in studies[name]['inputs'].items():assert sha(n)==h
    for name,owner in [('known_audit1','known1'),('real_audit2','real1')]:
        r=studies[name];assert r['result']=='independent_conditional_phase_audit_passed'
        assert r['producer_sha256']==sha(evidence/owner/'report.json')
        assert r['auditor_sha256']==sha(evidence/name/'executed_audit.py')
    assert studies['known_audit1']['known_controls_and_continuity_verified']
    assert studies['real_audit2']['harmonics']==1728 and studies['real_audit2']['all_aggregates_independently_verified']
    assert studies['real_audit2']['auditor_sha256']==sha(repo/'tools/audit_conditional_phase_feasibility_v1.py')
    assert studies['real_audit1']['result']=='failed'
    assert sha(evidence/'real_audit1/executed_audit.py')!=sha(evidence/'real_audit2/executed_audit.py')
    repair=load(evidence/'audit_repair.json');assert repair['runtime_CDF_representation_verified_without_gate_change']
    for name in ('known1','real1'):
        for row in studies[name]['cases']:
            folder=evidence/name/row['label']
            if name=='known1':
                if not row.get('rejected'):assert sha(folder/'transport.npz')==row['sha256']
            else:
                assert sha(folder/'inputs.npz')==row['input_sha256']
                for r in row['harmonics']:assert sha(folder/f'{r["order"]:03d}'/'transport.npz')==r['sha256']
    assert sha(evidence/'known1/continuous_control.npz')==studies['known1']['continuous_control_sha256']
    for name in ('review1','review2'):
        review=studies[name];assert review['result']=='conditional_phase_feasibility_figure_ready'
        for n,h in review['sources'].items():
            assert sha(evidence/name/'exact_sources'/n)==h
            if name=='review2':assert sha(repo/n)==h
        for n,h in review['inputs'].items():assert sha(n)==h
        assert sha(evidence/name/'figure_inputs.json')==review['figure_inputs_sha256']
        for n,h in review['images'].items():assert sha(evidence/name/n)==h
    assert studies['review1']['figure_inputs_sha256']==studies['review2']['figure_inputs_sha256']
    visual=load(evidence/'review2/visual_review.json')
    assert visual['scientific_figures_individually_viewed']==1 and visual['accepted_for_publication']
    assert visual['images_sha256']==review['images']
    assert not list(evidence.rglob('*.wav'))
    source=studies['real1']
    validation=dict(result='conditional_phase_feasibility_frozen',
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='Progress: requested ADI V6 hash-bound estimate, no synthesis change. This turn archive-verified/committed parent and constructs certified continuous conditional-phase class evidence.',
        known_controls=8,source_models=6,harmonics=1728,original_QMC_cases=18,original_QMC_draws_per_seed=4096,
        mean_band_complex_error=source['mean_band_complex_error'],
        class_inexact_harmonics=source['class_inexact_harmonics'],
        finite_amplitude_phase_agnostic_gap_harmonics=source['universal_finite_amplitude_gap_harmonics'],
        all24_band_coordinates_improve=all(a>b for a,b in zip(source['band_complex_errors']['parent_pooled'],source['band_complex_errors']['positive_probe'])),
        maximum_inverse_uniform_slope_bound=source['maximum_inverse_uniform_slope_bound'],
        maximum_inverse_product_slope_bound=source['maximum_inverse_product_slope_bound'],
        complete_LP_primal_dual_certificates_retained=True,training_prediction_not_audio=True,
        original_amplitude_and_continuous_phase_marginals_preserved_on_finite_draws=True,
        no_claim_of_universal_feasibility_or_bounded_audio_phase_speed=True,
        audits=dict(known=studies['known_audit1'],real=studies['real_audit2']),
        first_CDF_slope_audit_failure_exact_source_retained=True,
        repair=repair,scientific_figures_individually_viewed=1,
        review1_legend_occlusion_retained_review2_layout_only_data_exact=True,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,new_C_H=0,
        new_audio=False,runtime_default_driver_owned_take_room_changed=False,
        parent_and_old_F2_F3_hearings='independently pending; not repeated',old_68CTest_not_repeated=True,
        downloaded=False,pushed=False,physical_7_1_4=False,ADI_candidate_budget_claimed=False,
        full_goal='active',
        next='Find maximum-entropy/smooth interior conditional coupling at the same attainable moment, inspect actual slopes and amplitude-joint gaps, then generation through original observer; no sparse-LP audible promotion, blind rank/rho/strength sweep or new driver/spatial coupling. Full engines/states/Cport/physical7.1.4 remain incomplete.')
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])
    sources+=[n for n in names if ('conditional_phase' in n) and Path(n).suffix in ('.py','.md','.json')]
    sources+=list(studies['known1']['sources'])+['tools/research_archive_v1.py',
        'research/幅度条件相位可实现性V1.md','research/relative_phase_v1_plan.json',
        'research/relative_phase_v1_summary.json','research/stereo_phase_budget_v1_summary.json',
        'research/relative_phase_v1_listening.json','AGENTS.md','README.md',
        'handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    shutil.copy2(__file__,evidence/'executed_package.py')
    inputs=dict(data_AGENTS=a.workspace/'AGENTS.md',
        parent_manifest=parent/'manifest.json',parent_validation=parent/'validation.json',
        model_parent_manifest=a.workspace/'baselines/relative_phase_v1/manifest.json',
        frozen_C_build_source_zip=a.workspace/'baselines/F3_local_atlas_v1/source.zip')
    model_parent=a.workspace/'baselines/relative_phase_v1'
    for name in studies['real1']['inputs']:
        path=Path(name)
        if path.is_relative_to(model_parent):
            inputs['frozen_model_inputs/'+path.relative_to(model_parent).as_posix()]=path
    result=freeze(root,repo,sources,evidence,inputs,validation)
    verify(root);save(repo/'research/conditional_phase_feasibility_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',[
        'conditional_phase_feasibility_v1','baselines/conditional_phase_feasibility_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '8known;6source1728LP;18originalQMC;independent amplitudes/hats/quadrature/LPduals/scalarCDF;1figure',
        '670C-H82voice3F2/index exact;355class/153finite-amp gaps;trainingcoh .067913->.001828;steepslopes NOT audioaccepted;nohearingchange',
        'research/幅度条件相位可实现性V1.md | research/conditional_phase_feasibility_v1_summary.json',
        'baselines/conditional_phase_feasibility_v1/validation.json'])
    print(result)


if __name__=='__main__':main()
