"""Freeze signed stereo-dependence/window diagnostics and unchanged runtime."""
import argparse
import csv
import math
from pathlib import Path
import shutil
import subprocess
from research_archive_v1 import load,save,sha,freeze,verify,append_index


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verify',action='store_true')
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    evidence=a.workspace/'references/analysis/stereo_phase_budget_v1';root=a.workspace/'baselines/stereo_phase_budget_v1'
    if a.verify:
        m=verify(root);print(dict(result='archive_verified',files=m['file_count'],bytes=m['bytes']));return
    parent=a.workspace/'baselines/relative_phase_v1'
    assert sha(parent/'manifest.json')==load(repo/'research/relative_phase_v1_summary.json')['manifest_sha256']
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
    assert len(index)==671 and all(row[4]==protected['C_files_sha256.json'][row[0]] for row in index[1:])
    entries={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
    assert sha(repo/'handoff/C文件索引.csv')==entries['source/handoff/C文件索引.csv']
    phase_hearing=repo/'research/relative_phase_v1_listening.json'
    assert sha(phase_hearing)==entries['source/research/relative_phase_v1_listening.json']
    studies={n:load(evidence/n/'report.json') for n in ['known1','known_audit1','real1','real_audit1','real_audit2','review1','review2']}
    for name,expected in [('known1','stereo_budget_known_controls_ready'),('real1','six_source_stereo_budget_and_window_evidence_ready')]:
        r=studies[name];assert r['result']==expected
        for n,h in r['sources'].items():assert sha(repo/n)==sha(evidence/name/'exact_sources'/n)==h
        for n,h in r['inputs'].items():assert sha(n)==h
    assert len(studies['known1']['cases'])==7 and len(studies['real1']['cases'])==6
    for name,owner in [('known_audit1','known1'),('real_audit1','real1'),('real_audit2','real1')]:
        r=studies[name];assert r['result']=='independent_stereo_budget_audit_passed'
        assert r['producer_sha256']==sha(evidence/owner/'report.json') and r['auditor_sha256']==sha(evidence/name/'executed_audit.py')
    assert studies['known_audit1']['dense_real_quadratic_window_null_and_demeaning_verified']
    assert studies['real_audit2']['all_report_aggregates_independently_verified']
    assert studies['real_audit2']['auditor_sha256']==sha(repo/'tools/audit_stereo_phase_budget_v1.py')
    for row in studies['known1']['cases']:
        folder=evidence/'known1'/row['label'];assert sha(folder/'inputs.npz')==row['input_sha256']
        if 'budget_sha256' in row:assert sha(folder/'budget.npz')==row['budget_sha256']
    assert sha(evidence/'known1/small_window.npz')==studies['known1']['small_window_sha256']
    for row in studies['real1']['cases']:
        for q in row['QMC']:assert sha(evidence/'real1'/row['label']/f'budget_{q["seed"]}.npz')==q['sha256']
        assert sha(evidence/'real1'/row['label']/'window.npz')==row['window']['sha256']
    for name in ('review1','review2'):
        r=studies[name];assert r['result']=='stereo_budget_figures_ready'
        for n,h in r['sources'].items():assert sha(evidence/name/'exact_sources'/n)==h
        if name=='review2':assert all(sha(repo/n)==h for n,h in r['sources'].items())
        for n,h in r['inputs'].items():assert sha(n)==h
        for n,h in r['images'].items():assert sha(evidence/name/n)==h
    assert studies['review1']['images']['window_null.png']==studies['review2']['images']['window_null.png']
    visual=load(evidence/'review2/visual_review.json')
    assert visual['scientific_figures_individually_viewed']==2 and visual['accepted_for_final_publication']
    assert visual['images_sha256']==studies['review2']['images'] and visual['window_figure_exact']
    binding=load(evidence/'observation_binding.json');observer=Path(binding['original_observer_source'])
    assert sha(observer)==sha(repo/'tools/sound_dna/windowed.py')==binding['original_observer_sha256']
    geometry=a.workspace/'baselines/coefficient_geometry_v1'
    assert sha(geometry/'manifest.json')==binding['parent_geometry_manifest_sha256']==load(repo/'research/coefficient_geometry_v1_summary.json')['manifest_sha256']
    assert not list(evidence.rglob('*.wav'))
    study=studies['real1'];terms={}
    for key in ('amplitude_product','phase_marginal','association','denominator','phase_quantile_bias','phase_QMC_discrepancy'):
        values=[math.hypot(*v) for row in study['cases'] for v in row['average'][key]]
        terms[key]=dict(mean_absolute=sum(values)/len(values),maximum_absolute=max(values))
    validation=dict(result='stereo_phase_budget_and_observer_window_frozen',
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        previous_goal_turn='Progress: source-derived relative-phase models and paired audio frozen at6ceac43. This turn explains five remaining stereo regressions and qualifies the observation-window null.',
        known_controls=7,source_models=6,QMC_cases=18,QMC_draws=4096,
        known_audit=studies['known_audit1'],real_audit=studies['real_audit2'],
        regression_cases=study['regression_cases'],term_magnitudes=terms,
        mean_coherence_error=study['mean_coherence_error'],
        full_population_counterfactual_improves=study['population_counterfactual_improves_coordinates'],
        full_population_diagnostic_is_not_new_preset=True,full_signed_cancellations_preserved=True,
        original_observer_binding=binding,
        white_null_finite_curve_is_ratio_of_expected_moments_not_expected_sample_correlation=True,
        source_or_engine_time_law_identified=False,
        C_H_exact=670,voice_parameters_exact=82,F2_files_exact=3,C_index_exact=True,new_C_H=0,new_audio=False,
        scientific_figures_individually_viewed=2,review1_occlusion_and_exact_source_retained=True,
        review2_only_layout_title_and_window_PNG_exact=True,
        hearing=load(phase_hearing),parent_amplitude_and_old_F2_F3_hearings='independently pending; no repeat or new question',
        runtime_default_driver_owned_take_room_changed=False,old_68CTest_not_repeated=True,
        downloaded=False,pushed=False,physical_7_1_4=False,ADI_bound_claimed=False,full_goal='active',
        next='Qualify amplitude-conditioned relative phase, including moment feasibility and continuous generation; assess time through the original observer. No blind rank/rho/strength or bandwise winners. Preserve V6 layers, one driver and separate future spatial module; full multi-engine/state/C-port/physical7.1.4 still incomplete.')
    sources=[n for n in names if Path(n).suffix in ('.c','.h','.cmake','.in') or n.endswith('CMakeLists.txt')]
    sources+=list(protected['voice_files_sha256.json'])+list(protected['F2_files_sha256.json'])
    sources+=[n for n in names if 'stereo_phase_budget_v1' in n and n.startswith(('tools/','research/'))]
    sources+=list(studies['known1']['sources'])+['tools/research_archive_v1.py','tools/sound_dna/statistics.py',
        'research/左右幅相关联与观察窗口V1.md','research/relative_phase_v1_listening.json','AGENTS.md','README.md',
        'handoff/C文件索引.csv','handoff/开发留痕.md','handoff/研究续接.md','handoff/当前代码阅读入口.md']
    shutil.copy2(__file__,evidence/'executed_package.py')
    result=freeze(root,repo,sources,evidence,dict(data_AGENTS=a.workspace/'AGENTS.md',parent_manifest=parent/'manifest.json',
        parent_validation=parent/'validation.json',original_observer_manifest=geometry/'manifest.json',
        frozen_C_build_source_zip=a.workspace/'baselines/F3_local_atlas_v1/source.zip'),validation)
    verify(root);save(repo/'research/stereo_phase_budget_v1_summary.json',dict(validation,**result))
    append_index(repo/'handoff/阶段索引.csv',[
        'stereo_phase_budget_v1','baselines/stereo_phase_budget_v1/manifest.json',result['file_count'],result['manifest_sha256'],
        '7known;6source18QMC;signed4term+analyticCDFphase;fullpopulationGaussian;realwhiteRPwindow+densequadratic+finitegeometric;2figures',
        '670C-H82voice3F2/Cindex exact;5regressions association94.8..99.1projectionNOTenergy;fullcovdoesnotfix;whitewindowlag1.95;noaudio/hearingchange',
        'research/左右幅相关联与观察窗口V1.md | research/stereo_phase_budget_v1_summary.json','baselines/stereo_phase_budget_v1/validation.json'])
    print(result)


if __name__=='__main__':main()
