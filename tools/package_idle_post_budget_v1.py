"""Freeze actual POST conditional response and the remaining joint-moment gap."""
import argparse
import shutil
import subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/idle_post_budget_v1'
if a.stage=='verify':verify(root);print('Complete POST zero-budget evidence verified.');raise SystemExit
evidence=a.workspace/'references/analysis/idle_post_budget_v1'
observed=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json');plot=load(evidence/'plot1/report.json')
assert observed['result']=='all_POST_zero_budgets_and_TRAIN_allocation_complete_NO_promotion'
assert audit['result']=='all2048_POST_kernels_source_budget_inverse_and64jackknife_verified'
assert audit['input_report_sha256']==plot['input_report_sha256']==sha(evidence/'observe1/report.json')
assert plot['audit_sha256']==sha(evidence/'audit1/report.json')
assert sha(evidence/'observe1'/observed['data_file'])==observed['data_sha256']
assert observed['allocation']['generative'] and observed['allocation']['rank']==4
assert len(observed['jackknife_statuses'])==64 and set(observed['jackknife_statuses'])=={'positive_allocation'}
assert all(0<value<1 for value in observed['kappa_ratio_to_old'])
assert plot['all12_cross_under_source'] and observed['all_lag_curves_qualified'] is False
sources=set()
for name,digest in observed['sources'].items():
    assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name);sources.add(name)
for directory,name,executed in [('audit1','audit_idle_post_budget_v1.py','executed_auditor.py'),
                              ('plot1','plot_idle_post_budget_v1.py','executed_plot.py')]:
    assert sha(repo/'tools'/name)==sha(evidence/directory/executed);sources.add('tools/'+name)
assert len(plot['images'])==2
for image in plot['images']:
    assert sha(evidence/'plot1'/image['file'])==image['sha256']
    name='research/idle_post_budget_v1_'+image['file'];shutil.copy2(evidence/'plot1'/image['file'],repo/name);sources.add(name)
sources.update(['tools/package_idle_post_budget_v1.py','research/怠速共振后颗粒预算V1.md',
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
validation=dict(schema='vsl.idle-post-budget-freeze/1',
    result='positive_marginal_reallocation_BUT_all12_cross_gaps_remain',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),audit=audit,
    conditional_innovation_moments_direct=True,time_MC_origins=2048,time_MC_groups=64,
    time_MC_NOT_full_native_grid=True,all_lag_curves_qualified=False,
    analytic_observer_tail_evaluated_floating_NOT_formal_interval=True,all_full_FIR_retained=True,
    complete7term_budget=True,allocation=observed['allocation'],kappa_ratio_to_old=observed['kappa_ratio_to_old'],
    all64_leavegroup_allocations_positive=True,auto_TRAINfit_NOT_validation=True,
    new_cross_fraction_of_source=plot['new_cross_fraction_of_source'],all12_cross_under_source=True,
    both_complete_figures_viewed=True,unchanged_C_H=612,unchanged_old_voices=67,
    new_audio_or_profile=False,runtime_changed=False,old61_driving_tests_repeated=False,
    next='Actual POST time-varying joint4auto6cross feasibility and full lag verification preserving marginal/mean budgets. No stationaryPRE reuse/commontrigger/envelopecopy/oldkappa add; pending hearing/no duplicate or C promotion. Original commonphase and full goal remain.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation);verify(root)
save(repo/'research/idle_post_budget_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_post_budget_v1','baselines/idle_post_budget_v1/manifest.json',result['file_count'],result['manifest_sha256'],
    '3exactensembles/tail;2048allPOSTkernels/OA;source/15partitions/4inverse/64jackknife',
    'Marginalkappa reallocated but12crossgaps;timeMC/zeroONLY;612C-H67voices unchanged',
    'research/怠速共振后颗粒预算V1.md | research/idle_post_budget_v1_summary.json','baselines/idle_post_budget_v1/validation.json'])
print(result)
