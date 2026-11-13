"""Freeze complete lag observations, independent verification and source invariants."""
import argparse,shutil,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
root=a.workspace/'baselines/idle_joint_lag_v1'
if a.stage=='verify':verify(root);print('Complete idle lag evidence verified.');raise SystemExit
sys_path=a.workspace/'tools/python_deps'
import sys
sys.path.insert(0,str(sys_path))
import numpy as np
evidence=a.workspace/'references/analysis/idle_joint_lag_v1'
observed=load(evidence/'observe1/report.json');audit=load(evidence/'audit1/report.json')
plot=load(evidence/'plot1/report.json')
assert observed['result']=='all33_idle_lag_observations_complete_NO_sound_promotion'
assert audit['result']=='all33_lag_observations_660curves_and_response_support_verified'
assert audit['observations']==33 and audit['curves']==660
assert audit['input_report_sha256']==plot['input_report_sha256']==sha(evidence/'observe1/report.json')
assert plot['audit_sha256']==sha(evidence/'audit1/report.json')
assert plot['generated_blocks']==24 and plot['phase_controls']==6 and len(plot['images'])==3
sources=set()
for name,digest in observed['sources'].items():
    assert sha(repo/name)==digest==sha(evidence/'observe1/exact_sources'/name);sources.add(name)
for folder,name,executed in [('audit1','audit_idle_joint_lag_v1.py','executed_auditor.py'),
    ('plot1','plot_idle_joint_lag_v1.py','executed_plot.py')]:
    assert sha(repo/'tools'/name)==sha(evidence/folder/executed);sources.add('tools/'+name)
for image in plot['images']:
    assert sha(evidence/'plot1'/image['file'])==image['sha256']
    name='research/idle_joint_lag_v1_'+image['file']
    shutil.copy2(evidence/'plot1'/image['file'],repo/name);sources.add(name)
sources.update(['tools/package_idle_joint_lag_v1.py','research/怠速颗粒时间结构V1.md',
    'AGENTS.md','handoff/研究续接.md','handoff/开发留痕.md'])
inputs=dict(data_workspace_AGENTS=a.workspace/'AGENTS.md');tables={}
for name,digest in observed['parent_manifests'].items():
    path=a.workspace/'baselines'/name/'manifest.json';assert sha(path)==digest
    tables[name]={v['path']:v['sha256'] for v in load(path)['files']};inputs[name+'_manifest.json']=path
for path,digest in observed['inputs'].items():
    relative=Path(path).relative_to(a.workspace/'baselines')
    assert sha(path)==digest==tables[relative.parts[0]][Path(*relative.parts[1:]).as_posix()]
for name,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
    path=a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name;values=load(path);assert len(values)==count
    for source,digest in values.items():assert sha(repo/source)==digest,source
    inputs[name]=path
for row in observed['observations']:assert sha(evidence/'observe1'/row['file'])==row['sha256']
for row in observed['response_support']:
    first,last=row['q05_q95_frames'];assert abs(row['width90_ms']-(last-first)/48)<1e-12
with np.load(evidence/'observe1/expectation.npz') as archive:expectation={key:archive[key] for key in archive.files}
lags=expectation['lags'];mask=(abs(lags)>=384)&(abs(lags)<=960)
assert np.allclose(np.mean(expectation['normalized'][:,mask],axis=1),observed['expectation_summary']['late8_to20ms_mean'],atol=1e-12)
for lag,values in observed['expectation_summary']['selected'].items():
    assert np.allclose(expectation['normalized'][:,int(np.flatnonzero(lags==int(lag))[0])],values,atol=1e-12)
pairs=[(b,c) for b in range(4) for c in range(b,4)]
comparisons=[]
for j,(b,c) in enumerate(pairs):
    if b==c:continue
    item=dict(bands=[b,c],expectation_late=observed['expectation_summary']['late8_to20ms_mean'][j])
    for transform in ['raw','local40ms']:
        results=[]
        for portion in ['training','check']:
            source=next(v for v in observed['observations'] if v['label']==portion)['summary'][transform]['late8_to20ms_mean'][j]
            controls=[v['summary'][transform]['late8_to20ms_mean'][j] for v in observed['observations'] if v['kind']=='phase' and v['portion']==portion]
            assert source<0 and source<min(controls)
            results.append(dict(portion=portion,source=source,controls=controls,below_every_samePSD_control=True))
        item[transform]=results
    comparisons.append(item)
validation=dict(schema='vsl.idle-joint-lag-freeze/1',
    result='all33_lag_observations_audited_NOT_sound_promotion',
    parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),audit=audit,
    lag_points=81,source_portions=2,phase_controls=6,generated_blocks=24,pair_late_comparisons=comparisons,
    all6pairs_both_raw_and_local_late_negative_below_controls=True,
    all3_complete_plots_viewed=True,plan_direct_count_typo_preserved=True,
    new_audio_or_profile=False,runtime_changed=False,unchanged_C_H=612,unchanged_old_voices=67,
    old61_driving_tests_repeated=False,original_shared_phase_qualification_still_required=True,
    timbre_or_RPM_load_or_physical_phase_qualified=False,
    next='Known-qualified source-derived low-mode phase/difference amplitude features with train-only positive-power bounds and cross-portion prediction; no hardcoded27ms/RPM/PM-FM. Existing hearing pending/no repeated question or blind C promotion.')
result=freeze(root,repo,sorted(sources),evidence,inputs,validation);verify(root)
save(repo/'research/idle_joint_lag_v1_summary.json',dict(validation,**result))
append_index(repo/'handoff/阶段索引.csv',['idle_joint_lag_v1','baselines/idle_joint_lag_v1/manifest.json',
    result['file_count'],result['manifest_sha256'],
    '33observations/660fourth curves;all81points convolution/partition;knownall81+source11direct;24kernel supports',
    'Finite signed temporal association not engine timing/significance;no profile/audio/runtime;612C-H67voices unchanged',
    'research/怠速颗粒时间结构V1.md | research/idle_joint_lag_v1_summary.json',
    'baselines/idle_joint_lag_v1/validation.json'])
print(result)
