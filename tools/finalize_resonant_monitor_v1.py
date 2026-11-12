"""Publish the verified monitor boundary; preserve all prior source identities."""
import argparse,csv,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--verification',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];evidence=a.verification.parent
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
v=json.loads(a.verification.read_text(encoding='utf-8'))
assert v['result']=='native_monitor_technical_pass' and v['Ctests_passed']==50
for name,digest in v['source_sha256'].items():assert sha(repo/name)==sha(evidence/'exact_sources'/name)==digest,name
for name,digest in v['input_sha256'].items():
    path=evidence/'prior_C_index.csv' if Path(name)==repo/'handoff/C文件索引.csv' else Path(name)
    assert sha(path)==digest,name
for row in v['commands']:assert row['exit_code']==0 and sha(evidence/row['log'])==row['sha256']
for name,digest in v['binaries'].items():assert sha(evidence/name)==digest
for row in v['device']+v['dry_comparisons']:assert sha(evidence/row['file'])==row['sha256']
qa=evidence/'visual_qa.json';visual=json.loads(qa.read_text(encoding='utf-8'));assert visual['result']=='pass'
for name,digest in visual['screenshots'].items():assert sha(evidence/name)==digest
with (evidence/'prior_C_index.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
assert len(rows)==500
for row in rows:assert sha(repo/row['文件'])==row['SHA-256']
roles=dict(render='完整持续声源启停淡变／控制跟随／一次输出，实时无I/O或分配',
           models='五个既有参数配方非实时事务加载及拥有模型',
           audio='共享立体声设备宿主及成功提交后的有界调试控制记录',
           ui='简洁原生控件与非实时模型切换，默认停止',
           ui_checks='程序内部控件消息自检与自身窗口截图，不是人工鼠标验收',
           checks='五配方和监听边界契约',verify='短静音设备／实际采用帧重现／原配方dry导出')
added=[]
for folder in ('modules/resonant_monitor','experiments/resonant_monitor_v1'):
    for path in sorted((repo/folder).iterdir()):
        if path.suffix not in ('.c','.h'):continue
        name=path.relative_to(repo).as_posix();added.append(name)
        target='resonant_monitor' if folder.startswith('modules') else 'VslResonantMonitor'+('_checks' if path.stem=='checks' else '_verify' if path.stem=='verify' else '')
        rows.append(dict(zip(('文件','模块','构建归属','职责','SHA-256'),(name,'完整声源独立监听',target,roles[path.stem],sha(path)))))
assert len(added)==11 and len(rows)==511
a.out.mkdir(parents=True,exist_ok=False)
index=repo/'handoff/C文件索引.csv'
with index.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
summary=dict(schema='vsl.resonant-monitor-summary/1',date='2026-11-12',result='native_monitor_technical_pass',
    prior_C_H_unchanged=500,new_C_H=11,C_H_rows=511,C_H_index_sha256=sha(index),Ctests=50,
    native_host=True,default_stopped=True,recipe_count=5,
    device_runs=[dict(name=row['name'],frames=row['frames'],exact_replay=row['offline_float_equal'],queue_empty=row['queue_empty'],budget_exceeded=row['budget_exceeded'],render_max_ms=row['render_max_ms']) for row in v['device']],
    dry_comparisons=v['dry_comparisons'],visual_qa=True,manual_mouse_verification=False,
    driver_or_take_or_existing_default_changed=False,new_parameters_or_room_or_PCM=False,
    new_listening_acceptance=False,idle='pending original audition; RPM and thermal state unconfirmed',
    acceleration='existing driver/atlas functional; full RPM/load timbre map incomplete',
    evidence_sha256={str(path.relative_to(a.workspace)).replace('\\','/'):sha(path) for path in (a.verification,qa)},limits=v['limits'])
for path in (a.out/'report.json',repo/'research/resonant_monitor_v1_summary.json'):
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(__file__,a.out/'executed_finalize.py')
print(json.dumps(dict(result=summary['result'],C_H=511,Ctests=50,device_runs=summary['device_runs'])))
