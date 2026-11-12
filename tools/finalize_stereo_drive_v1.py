"""Bind successful stereo integration, prior failed checks and source diagnostics."""
import argparse,csv,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','verification','ui-proof','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
v=json.loads((a.verification/'report.json').read_text(encoding='utf-8'))
assert v['result']=='stereo_driver_technical_pass' and v['Ctests_passed']==53
u=json.loads((a.ui_proof/'report.json').read_text(encoding='utf-8'))
assert u['result']=='ui_selector_technical_pass' and u['source_proof_sha256']==sha(a.verification/'report.json')
for name,digest in u['sources'].items():assert sha(repo/name)==digest==sha(a.ui_proof/'exact_sources'/name),name
for name,digest in u['evidence_sha256'].items():assert sha(a.ui_proof/name)==digest,name
for name,digest in v['sources'].items():
    assert sha(a.verification/'exact_sources'/name)==digest,name
    if name not in u['sources']:assert sha(repo/name)==digest,name
for name,digest in v['inputs'].items():assert sha(repo/name)==digest,name
for name,digest in v['evidence_sha256'].items():assert sha(a.verification/name)==digest,name
with (a.verification/'prior_C_index.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
assert len(rows)==529
modified=[]
for row in rows:
    now=sha(repo/row['文件'])
    if now!=row['SHA-256']:modified.append(row['文件']);row['SHA-256']=now
assert set(modified)==set(v['modified_prior_C_H'])|{'experiments/drive_resonance_v1/ui_checks.c'}
roles={
    'modules/drive_resonance/bank.h':'同一锚点库的Rdt／双声道核类型与拥有参数接口',
    'modules/drive_resonance/bank.c':'非实时堆暂存事务构造、稳定校验、显式缺锚点',
    'modules/drive_resonance/voice.h':'同一DNA坐标的双核连续细节接口',
    'modules/drive_resonance/voice.c':'保留Rdt相位与seed；双声道递推／共享支持／量平滑',
    'modules/atlas_take_io/codec.c':'schema7显式小端序、拥有双核参数与稳定证书、严格身份',
    'experiments/atlas_monitor_v1/ui.c':'同一驾驶窗口／滑条，双声道趋稳研究入口与录放',
    'experiments/drive_resonance_v1/device.c':'原生静音双核台架／踏板／自包含录放与取消',
    'experiments/drive_resonance_v1/checks.c':'原Rdt相位／支持／零路径及schema7契约',
    'experiments/atlas_take_v1/checks.c':'拥有资产／回放／schema7损坏与事务文件契约',
    'experiments/drive_resonance_v1/ui_checks.c':'两研究窗口自身控件、语境下拉框、滑条与截图核查'}
keys=list(rows[0]);assert len(keys)==5
for row in rows:
    if row['文件'] in roles:row[keys[3]]=roles[row['文件']]
name='experiments/stereo_drive_v1/checks.c'
rows.append(dict(zip(keys,(name,'双声道驾驶契约','VslStereoDrive_checks','混合核／缺口／oracle／零路径／拥有参数与2-12一致',sha(repo/name)))))
index=repo/'handoff/C文件索引.csv'
with index.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');writer.writeheader();writer.writerows(rows)
assert len(rows)==530
joint=a.workspace/'references/analysis/stereo_joint_v1/analysis1'
j=json.loads((joint/'report.json').read_text(encoding='utf-8'))
assert j['result']=='lossless_stereo_correction_not_qualified' and not j['qualified']
for name,digest in j['sources'].items():assert sha(repo/name)==digest==sha(joint/'exact_sources'/name),name
for name,digest in j['inputs'].items():assert sha(Path(name))==digest,name
inspection=a.workspace/'references/analysis/dyno_tail_v1/inspect1'
ir=json.loads((inspection/'report.json').read_text(encoding='utf-8'));source=ir['sources']['D']
assert sha(Path(source['video']))==source['video_sha256']
for row in source['frames']+source['boards']:assert sha(inspection/'D'/row['file'])==row['sha256']
annotation=dict(schema='vsl.dyno-tail-observation/1',date='2026-11-12',
    report_sha256=sha(inspection/'report.json'),video_sha256=source['video_sha256'],
    frames=len(source['frames']),visually_inspected_boards=[v['file'] for v in source['boards']],
    observations=[dict(seconds=[32.032,52.052],description='Car strapped on dyno, rear wheel visibly blurred/spinning in inspected frames'),
        dict(seconds=40.04,description='Visible blue exhaust plume; caption HERE COME THE FLAMES. No trigger/physics inference.'),
        dict(seconds=[54.054,58.058],description='Black outro then logo')],
    decision='No stable idle established in these coarse frames. No RPM/state/profile exported.',
    not_established=['Screen units and calibrated RPM','Pedal/load/fuel state or exact backfire trigger','A/V synchronization, continuous unedited interval or warm-idle identity'])
(repo/'research/dyno_tail_v1_annotations.json').write_text(json.dumps(annotation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
summary=dict(schema='vsl.stereo-drive-summary/1',date='2026-11-12',result=v['result'],
    C_H_rows=530,unchanged_prior_C_H=519,modified_prior_C_H=modified,new_C_H=1,Ctests_passed=53,
    C_H_index_sha256=sha(index),schema_version=7,control_fields=28,
    driver_integrated=True,native_integrated=True,owned_take_integrated=True,
    context='A startup-settling cabin, not confirmed warm idle/exterior',parameters_unchanged=True,
    devices=v['devices'],ui=u['ui'],zero_regression=v['legacy'],
    diagnostic_result=j['result'],diagnostic_heldout_improvements=[h['heldout_shape_improvement'] for h in j['halves']],
    diagnostic_necessary_feasible=[h['necessary_feasible'] for h in j['halves']],
    moving35_complete_recipe_in_driver=False,listening_accepted=False,full_idle_or_acceleration_calibrated=False,
    limits=v['limits'],evidence_sha256={path.relative_to(a.workspace).as_posix():sha(path) for path in
        (a.verification/'report.json',a.ui_proof/'report.json',joint/'report.json',inspection/'report.json',
         a.workspace/'references/analysis/stereo_drive_v1/before1/snapshot.json')})
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_finalize.py')
for path in (a.out/'summary.json',repo/'research/stereo_drive_v1_summary.json'):
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=summary['result'],C_H=530,Ctests=53,modified=len(modified))))
