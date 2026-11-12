"""Publish kernel parity and source-context evidence, preserving executed versions."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--verification',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
read=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
a.out.mkdir(parents=True,exist_ok=False)
root=a.workspace/'references/analysis/resonant_detail_c_v1'
verified=a.verification.parent
report=read(a.verification)
assert report['result']=='C_kernel_and_cross_language_parity_pass' and report['Ctests_passed']==48
for name,digest in report['source_sha256'].items():
    assert sha(verified/'exact_sources'/name)==digest,name
    # Documentation can describe the completed check after it ran; DSP/tools cannot drift.
    if not name.endswith('.md'):assert sha(repo/name)==digest,name
for name,digest in report['input_sha256'].items():assert sha(Path(name))==digest,name
for row in report['comparisons']:assert sha(verified/row['output_file'])==row['output_sha256']
assert sha(verified/'VslResonantDetail_probe.exe')==report['probe_sha256']
for row in report['commands']:
    assert row['exit_code'] in (0,2) and sha(verified/row['log'])==row['sha256']
contract=report
if 'reused_contract_proof' in report:
    reused=report['reused_contract_proof']
    assert sha(Path(reused['file']))==reused['sha256']
    contract=read(reused['file'])
latest_test=next(row for row in contract['commands'] if row['argv'][0]=='ctest')
assert latest_test['exit_code']==0
proof=read(root/'verify1/report.json')
for row in proof['commands']:
    assert row['exit_code']==0 and sha(root/'verify1'/row['log'])==row['sha256']
assert sha(root/'verify1/exact_sources/tools/verify_resonant_detail_c_v1.py')==proof['source_sha256']['tools/verify_resonant_detail_c_v1.py']
with (verified/'prior_C_index.csv').open(encoding='utf-8-sig') as f:prior=list(csv.DictReader(f))
old=[row for row in prior if not row['文件'].startswith(('modules/resonant_detail/','modules/resonant_detail_io/','experiments/resonant_detail_c_v1/'))]
assert len(old)==478
for row in old:assert sha(repo/row['文件'])==row['SHA-256']
rows=list(old)
roles={
    'profile':'非实时参数、Schur极点边界和连续相位能量边界校验',
    'envelope':'调用者相位下的周期功率包络及非实时正值校验',
    'excitation':'分频带独立xorshift64star与BoxMuller激励',
    'filter':'AR及SOS的有状态连续滤波，不含IO或分配',
    'voice':'读取外部主声相位、逐带生成及L/R参数混合，无内部转速时钟'}
new=[]
for folder in ('modules/resonant_detail','modules/resonant_detail_io','experiments/resonant_detail_c_v1'):
    for path in sorted((repo/folder).iterdir()):
        if path.suffix not in ('.c','.h'):continue
        name=path.relative_to(repo).as_posix();new.append(name)
        if folder.endswith('_io'):module,target,role='连续共振参数IO','resonant_detail_io','非实时UTF8/有界参数读取，失败时保留旧模型'
        elif folder.startswith('experiments/'):module,target,role='连续共振C验证','VslResonantDetail_'+path.stem,'独立离线导出或契约验证，不在默认驾驶链'
        else:module,target,role='连续共振细节','resonant_detail',roles[path.stem]
        rows.append(dict(zip(('文件','模块','构建归属','职责','SHA-256'),(name,module,target,role,sha(path)))))
assert len(new)==14 and len(rows)==492
index=repo/'handoff/C文件索引.csv'
with index.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
summary=dict(schema='vsl.resonant-detail-c-summary/1',date='2026-11-12',result='modular_C_kernel_parity_pass_only',
    prior_C_H_unchanged=478,new_C_H=14,C_H_index_rows=492,C_H_index_sha256=sha(index),Ctests=48,
    max_unit_band_error=max(max(v['max_unit_band_error']) for v in report['comparisons']),
    max_stereo_error_FS=max(v['max_stereo_error_FS'] for v in report['comparisons']),
    actual_comparisons=len(report['comparisons']),profiles=['moving_35','idle_add','idle_35'],
    phase_and_engine_clock_owned_by_caller=True,kernel_does_not_allocate_or_perform_IO=True,
    no_source_PCM_or_timeline=True,new_fitting=False,default_driver_take_UI_changed=False,
    source_context_listening_status=dict(moving35='held offline recipe; C detail kernel parity only',idle='pending original question'),
    full_mixture_parity=False,driver_integration=False,native_listening=False,device_or_longrun=False,
    public_namespace='Rdt types,rdt_ functions,RDT_ constants; coexistence with residual_dense compiled and linked',
    retained_failure='verify1 valid48-pass log regex failed; verify2 reused proof; interface_review1 RD namespace collision; verify3 missing old library target fixed; verify4 passed48tests/9comparisons, final2 pre-regeneration cache hash failed; verify5 mistakenly rejected expected2 invalid-input logs during proof reuse; verify6 binds post-build cache and reuses unchanged verify4 build/CTest proof',
    evidence_sha256={str(path.relative_to(a.workspace)).replace('\\','/'):sha(path) for path in
        (root/'export1/report.json',root/'verify1/report.json',root/'verify2/report.json',root/'interface_review1/report.json',root/'verify3/report.json',root/'verify4/report.json',root/'final2/report.json',root/'verify5/report.json',a.verification)},limits=report['limits'])
for target in (a.out/'report.json',repo/'research/resonant_detail_c_v1_summary.json'):
    target.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

sport=a.workspace/'references/analysis/sport_acceleration_v1'
observed=read(sport/'analysis2/report.json');before=read(sport/'analysis1/report.json')
assert observed['result']=='context_and_local_diagnostic_observed'
assert observed['low_case']==before['low_case'] and observed['raw_budgets']==before['raw_budgets']
for name,digest in observed['source_sha256'].items():assert sha(repo/name)==sha(sport/'analysis2/exact_sources'/name)==digest
for name,digest in observed['input_sha256'].items():assert sha(Path(name))==digest
shutil.copy2(sport/'analysis2/context.png',repo/'research/sport_acceleration_v1_context.png')
low=observed['low_case'];primary=low['references']['5']['evidence']
sport_summary=dict(schema='vsl.sport-acceleration-summary/1',date='2026-11-12',result='new_context_only_not_new_DNA',
    inspected_frame_files=48,visible_edit_seconds=[57.75,58],display_downshifts=[[4,3],[3,2]],
    low_case=low['case'],local_diagnostic_gate=False,
    coarse_path_status={k:v['status'] for k,v in low['references'].items()},
    observed_primary_root_range_hz=primary['correction']['inferred_root_hz_range'],
    primary_separate_carrier_gate=primary['correction']['independent_agreement'],
    missing_separate_path_references=[3,7],new_model=False,generic_phase_status='not_passed_unchanged',
    raw_budgets=observed['raw_budgets'],runtime_or_state_policy_changed=False,
    preserved_attempts=['inspect1','inspect2','analysis1','analysis2'],
    entry_guard_revision='analysis2 allows future C index growth; numerical observations equal analysis1',
    evidence_sha256={str(path.relative_to(a.workspace)).replace('\\','/'):sha(path) for path in
        (sport/'inspect1/report.json',sport/'inspect2/report.json',sport/'analysis1/report.json',sport/'analysis2/report.json')},
    limits=observed['limits'])
(repo/'research/sport_acceleration_v1_summary.json').write_text(json.dumps(sport_summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(__file__,a.out/'executed_finalize.py')
print(json.dumps(dict(kernel=summary['result'],C_H=492,Ctests=48,max_error=summary['max_stereo_error_FS'],sport=sport_summary['result'])))
