"""Freeze limited white-joint rejections and the concrete valid-audio next step."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/idle_post_joint_v1'
if a.stage=='verify':verify(root);print('Complete actual POST joint evidence verified.');raise SystemExit
evidence=a.workspace/'references/analysis/idle_post_joint_v1'
observed=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json');plot=load(evidence/'plot1/report.json')
assert observed['result']=='both_actual_POST_joint_families_examined_NO_promotion'
assert audit['result']=='all2048_full_tensor_operators_and_both64group_feasibilities_verified'
assert audit['input_report_sha256']==plot['input_report_sha256']==sha(evidence/'observe1/report.json')
assert plot['audit_sha256']==sha(evidence/'audit1/report.json')
assert sha(evidence/'observe1'/observed['data_file'])==observed['data_sha256']
for name,row in observed['families'].items():
    assert row['solution']['status']=='latent_indefinite_REJECTED' and row['solution']['rank']==10
    assert len(row['leave_groups'])==64 and all(z['status']=='latent_indefinite_REJECTED' for z in row['leave_groups'])
    assert row['minimum_eigenvalue_time_MC']['approx_point95'][1]<0
    assert sha(evidence/'observe1'/(name+'_train.json'))==row['train_solution_sha256']
sources=set()
for name,digest in observed['sources'].items():
    assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name);sources.add(name)
for directory,name,executed in [('audit1','audit_idle_post_joint_v1.py','executed_auditor.py'),
                               ('plot1','plot_idle_post_joint_v1.py','executed_plot.py')]:
    assert sha(repo/'tools'/name)==sha(evidence/directory/executed);sources.add('tools/'+name)
assert len(plot['images'])==1
for image in plot['images']:
    assert sha(evidence/'plot1'/image['file'])==image['sha256']
    name='research/idle_post_joint_v1_'+image['file'];shutil.copy2(evidence/'plot1'/image['file'],repo/name);sources.add(name)
sources.update(['tools/package_idle_post_joint_v1.py','research/怠速共振后共同激励V1.md',
                'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs=dict(data_workspace_AGENTS=a.workspace/'AGENTS.md');tables={}
for name,digest in observed['parent_manifests'].items():
    path=a.workspace/'baselines'/name/'manifest.json';assert sha(path)==digest
    inputs[name+'_manifest.json']=path;tables[name]={row['path']:row['sha256'] for row in load(path)['files']}
for path,digest in observed['inputs'].items():
    relative=Path(path).resolve().relative_to((a.workspace/'baselines').resolve())
    assert sha(path)==digest==tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
for name,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    path=a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name;values=load(path);assert len(values)==count
    for source,digest in values.items():assert sha(repo/source)==digest,source
    inputs[name]=path
validation=dict(schema='vsl.idle-post-joint-freeze/1',
    result='BOTH_limited_white_joint_families_indefinite_for_sampled_POST_budget',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),audit=audit,
    all2048origins_all100columns=True,all_signed_cross_terms=True,all_coefficient_tail_bounds=True,
    both64_leave_groups_indefinite=True,source_level_impossibility_claim=False,full_lag_qualified=False,
    no_PSD_projection_or_rate_sweep=True,all_algebraic_invalid_predictions_retained=True,
    figure_viewed=True,unchanged_C_H=612,unchanged_old_voices=67,
    new_audio_or_profile=False,runtime_changed=False,old61_driving_tests_repeated=False,
    next='Stop white-family permutations. Render legal priorPOSTq+allocatedindependentkappa vs staticGaussian/sparse-only oldkappa, original3seeds/12s/4blocks/samegain/dry, independent fullwave+zeroidentity+all81rawlag/source checks; report gaps, no duplicate hearing question/C promotion. Original commonphase/full goal remain.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation);verify(root)
save(repo/'research/idle_post_joint_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_post_joint_v1','baselines/idle_post_joint_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    'OldexactGaussian/Poisson+6;newtensor+6;2048all100columns/OA/permutations/bounds/SVD/64groups',
    'Both limitedwhitefamilies invalid;timeMC/zeroONLY;612C-H67voices unchanged',
    'research/怠速共振后共同激励V1.md | research/idle_post_joint_v1_summary.json','baselines/idle_post_joint_v1/validation.json'])
print(result)
