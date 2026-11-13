"""Freeze both honest phase hypotheses, complete audio, audits, review and UI evidence."""
import argparse,shutil,subprocess,sys,struct,hashlib
sys.path.insert(0,"E:/VehicleSoundLab/tools/python_deps")
import numpy as np
import soundfile as sf
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/idle_phase_recipe_v1'
if a.stage=='verify':verify(root);print('Both idle phase recipes and all evidence verified.');raise SystemExit
evidence=a.workspace/'references/analysis/idle_phase_recipe_v1';sources=set()
fit=load(evidence/'fit1/report.json');assert fit['result']=='source_VAR2_stable_pending_waveform_and_listening'
assert sha(evidence/'fit1/model.json')==fit['model_sha256']
first=load(evidence/'render1/report.json');second=load(evidence/'render2/report.json')
for old,new in zip(first['renders'],second['renders']):
    assert old['seed']==new['seed'] and old['seconds']==new['seconds']
    for name in ['old_main','static_detail','post_detail','static','post']:
        p=evidence/'render1'/old['files'][name]['file'];q=evidence/'render2'/new['files'][name]['file']
        x,fs=sf.read(p,always_2d=True);y,gs=sf.read(q,always_2d=True)
        assert fs==gs==48000 and np.array_equal(x,y)
        def chunks(path):
            raw=path.read_bytes();items={};i=12
            while i+8<=len(raw):
                tag=raw[i:i+4];size=struct.unpack_from('<I',raw,i+4)[0]
                items[tag]=raw[i+8:i+8+size];i+=8+size+(size%2)
            return items
        ca,cb=chunks(p),chunks(q);assert ca.keys()==cb.keys()
        for tag in ca:
            if tag==b'PEAK':assert ca[tag][:4]+ca[tag][8:]==cb[tag][:4]+cb[tag][8:]
            else:assert ca[tag]==cb[tag]

for directory in ['fit1','render1','render2']:
    report=load(evidence/directory/'report.json')
    for name,digest in report['sources'].items():
        assert sha(repo/name)==digest==sha(evidence/directory/'exact_sources'/name);sources.add(name)
for version in [1,2]:
    rendered=load(evidence/f'render{version}/report.json');audit=load(evidence/f'audit{version}/report.json')
    review=load(evidence/f'review{version}/report.json');plot=load(evidence/f'plot{version}/report.json')
    assert rendered['result']=='new_stationary_idle_phase_audio_pending_independent_audit'
    assert audit['result']=='passed' and audit['input_report_sha256']==sha(evidence/f'render{version}/report.json')
    assert review['audit_sha256']==plot['audit_sha256']==sha(evidence/f'audit{version}/report.json')
    assert review['input_report_sha256']==plot['input_report_sha256']==sha(evidence/f'render{version}/report.json')
    assert review['common_gain']==1.0 and len(review['clips'])==30
    assert sha(evidence/f'render{version}/model.json')==rendered['model_sha256']
    for row in rendered['renders']:
        for entry in row['files'].values():assert sha(evidence/f'render{version}'/entry['file'])==entry['sha256']
        assert sha(evidence/f'render{version}'/row['motion_file'])==row['motion_sha256']
        assert len(row['blocks'])==4*(row['seconds']//3)
    for row in review['clips']:assert sha(evidence/f'review{version}'/review['files'][row['key']])==row['sha256']
    for row in audit['phase_observations']:assert sha(evidence/f'audit{version}'/row['file'])==row['sha256']
    for row in plot['images']:assert sha(evidence/f'plot{version}'/row['file'])==row['sha256']
    auditor='tools/audit_idle_phase_'+('spectral_' if version==2 else '')+'recipe_v1.py'
    for name,directory,executed in [(auditor,f'audit{version}','executed_auditor.py'),
        ('tools/review_idle_phase_recipe_v1.py',f'review{version}','executed_review.py'),
        ('tools/idle_phase_recipe_v1/review.html',f'review{version}','executed_template.html'),
        ('tools/plot_idle_phase_recipe_v1.py',f'plot{version}','executed_plot.py')]:
        assert sha(repo/name)==sha(evidence/directory/executed);sources.add(name)
browser=load(evidence/'browser3/report.json');assert browser['result']=='passed' and browser['metadata_combinations']==30
assert load(evidence/'browser2/report.json')['result']=='failed'
for name,directory in [('tools/check_idle_phase_recipe_v1.cjs','browser2'),('tools/check_idle_phase_recipe_v1_2.cjs','browser3')]:
    assert sha(repo/name)==sha(evidence/directory/'executed_check.cjs');sources.add(name)
for filename in ['phase_statistics.png','longrun_bands.png']:
    name='research/idle_phase_recipe_v1_'+filename;shutil.copy2(evidence/'plot2'/filename,repo/name);sources.add(name)
name='research/idle_phase_recipe_v1_profile.json';shutil.copy2(evidence/'render2/model.json',repo/name);sources.add(name)
sources.update(['tools/package_idle_phase_recipe_v1.py','tools/package_idle_phase_recipe_v1_2.py','research/怠速声线关联生成V1.md',
                'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs=dict(data_workspace_AGENTS=a.workspace/'AGENTS.md')
parents=['idle_closure_evidence_v1','fixed_source_profiles_v1','idle_positive_power_v1','idle_post_budget_v1','idle_excitation_moments_v1']
tables={}
for name in parents:
    path=a.workspace/'baselines'/name/'manifest.json';inputs[name+'_manifest.json']=path
    tables[name]={v['path']:v['sha256'] for v in load(path)['files']}
for report in [fit,load(evidence/'render1/report.json'),load(evidence/'render2/report.json')]:
    for key,row in report['inputs'].items():
        path=Path(key) if isinstance(row,str) else Path(row['path']);digest=row if isinstance(row,str) else row['sha256']
        assert sha(path)==digest;rel=path.relative_to(a.workspace/'baselines')
        assert digest==tables[rel.parts[0]][Path(*rel.parts[1:]).as_posix()]
for name,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    path=a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name;rows=load(path);assert len(rows)==count
    for source,digest in rows.items():assert sha(repo/source)==digest
    inputs[name]=path
validation=dict(schema='vsl.idle-phase-recipe-freeze/1',result='optional_joint_spectral_idle_candidate_pending_listening',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    VAR2_retained_NOT_adopted_reason='Overly oscillatory phase lag curves; not a hearing result',
    both_render_and_audit_reports={str(v):sha(evidence/f'audit{v}/report.json') for v in [1,2]},
    full_wave_seconds_first_seed=180,other2seed_seconds=24,seeds=[149921,277139,381611],
    all_wave_samples_finite_unclipped=True,all_main_and_q_native_samples_independent=True,
    independent_audio_FIR_scope='selected direct dot-product points, not every convolution sample',
    all501coordinate_lags=True,all60longrun_audio_blocks=True,
    review_url=load(evidence/'review2/report.json')['url'],review_clips=30,shared_gain=1.0,
    browser=browser,first_browser_harness_failure_retained=True,all4research_plots_and_both_UI_sizes_viewed=True,
    original3frequencies_hz=load(evidence/'render2/report.json')['original_three_frequencies_hz'],
    new3mean_frequencies_hz=load(evidence/'render2/report.json')['generated_mean_carrier_frequencies_hz'],
    statistical_phase_profile='research/idle_phase_recipe_v1_profile.json',
    source_phase_PCM_trajectory_replayed=False,actual_crank_RPM_or_longterm_physical_coupling_identified=False,
    source_check_and_long_lag_discrepancies_remain=True,unchanged_C_H=612,unchanged_old_voices=67,
    all15original_recipe_buses_samples_and_data_chunks_exact=True,
    float_WAV_PEAK_timestamp_only_difference=True,first_packaging_assertion_preserved=True,
    runtime_changed=False,listening_accepted=False,
    next='Judge new offline source-derived idle candidate before C promotion; no duplicate question. Preserve accepted moving35/oldidle/takes. Continue source texture and actual one-clock driving qualification, original commonphase36/all17/full33/individual14k/originalE and full goal remain active.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation);verify(root)
save(repo/'research/idle_phase_recipe_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_phase_recipe_v1','baselines/idle_phase_recipe_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'VAR2+jointFIR/all3seeds/180s+24s+24s/allmain-q/501lags/60blocks/30HTTPbrowser',
    'Offlinecandidate/VAR2overperiodic/sourcecheck-longlaggaps/612C-H67oldvoicesunchanged',
    'research/怠速声线关联生成V1.md | research/idle_phase_recipe_v1_summary.json','baselines/idle_phase_recipe_v1/validation.json'])
print(result)
