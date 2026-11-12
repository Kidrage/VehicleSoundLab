"""Publish the verified optional driving detail boundary and current C index."""
import argparse,csv,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--verification',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];evidence=a.verification.parent
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
v=json.loads(a.verification.read_text(encoding='utf-8'));assert v['result']=='driving_resonant_detail_technical_pass' and v['Ctests_passed']==51
assert len(v['modified_prior_C_H'])==19 and len(v['legacy'])==3 and sum(row['WAV_bytes_equal'] for row in v['legacy'])==84
assert v['source_and_front_2_12_exact'] and v['device']['record_hash']==v['device']['play_hash']
for name,digest in v['source_sha256'].items():assert sha(repo/name)==sha(evidence/'exact_sources'/name)==digest,name
for name,digest in v['input_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in v['evidence_sha256'].items():assert sha(evidence/name)==digest,name
for row in v['commands']:assert row['exit_code']==row['expected'] and sha(evidence/row['log'])==row['sha256']
qa=evidence/'visual_qa.json';visual=json.loads(qa.read_text(encoding='utf-8'));assert visual['result']=='pass' and sha(evidence/'ui/window.png')==visual['screenshot_sha256']
with (evidence/'prior_C_index.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
assert len(rows)==511
for row in rows:
    digest=sha(repo/row['文件'])
    assert (digest!=row['SHA-256'])==(row['文件'] in v['modified_prior_C_H']),row['文件']
    row['SHA-256']=digest
roles=dict(bank='非实时拥有逐DNA锚点连续共振参数／缺失标记／局部工程范围',
    voice='消费实际主DNA相位及锚点权重，持续共振／预热原点／局部淡变，无独立RPM时钟',
    checks='独立相位／两种合成控制／缺失与静音时钟／零量旁路／schema6拥有模型2和12契约',
    device='同一原生音频宿主的静音设备录放、清空外部模型及取消验证',
    ui_checks='程序内部控件消息和自身窗口截图，非人工鼠标验收')
added=[]
for folder in ('modules/drive_resonance','experiments/drive_resonance_v1'):
    for path in sorted((repo/folder).iterdir()):
        if path.suffix not in ('.c','.h'):continue
        name=path.relative_to(repo).as_posix();added.append(name)
        target='drive_resonance' if folder.startswith('modules') else 'VslAtlasMonitor' if path.stem=='ui_checks' else 'VslDriveResonance_'+path.stem
        rows.append(dict(zip(('文件','模块','构建归属','职责','SHA-256'),(name,'统一驾驶连续共振细节',target,roles[path.stem],sha(path)))))
assert len(added)==8 and len(rows)==519;a.out.mkdir(parents=True,exist_ok=False)
index=repo/'handoff/C文件索引.csv'
with index.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
summary=dict(schema='vsl.driving-resonant-detail-summary/1',date='2026-11-12',result='optional_driving_detail_technical_pass',
    C_H_rows=519,new_C_H=8,modified_prior_C_H=19,unchanged_prior_C_H=492,C_H_index_sha256=sha(index),Ctests=51,
    legacy_WAV_byte_exact=84,legacy_trace_byte_exact=3,one_main_phase=True,aligned_prewarm=True,
    take_schema=6,control_fields=28,owned_parameters=True,source_and_front_2_12_exact=True,remaining10zero=True,
    device=v['device'],UI=v['ui'],visual_qa=True,manual_mouse_verified=False,
    moving35_not_tuned=True,real_parameter_context='A stationary low idle_add only; pending existing listening question',
    old_schema5_player_preserved=True,new_listening_acceptance=False,full_idle_or_loaded_acceleration_calibrated=False,
    attempts=['before1 preserves prior driver/player and actual schema5 take',
        'verify1 new driver contract passed; three old 27-field assertions failed',
        'verify2 updates field assertions;51tests/84WAV/device/take/UI pass',
        'verify3 aligns prewarm origin for future nonzero-offset anchors and strengthens independent filter-state oracle;full proof rerun passes',
        'wrap_boundary1 reproduces a tiny-negative phase rounding to1;verify4 canonicalizes phase to[0,1), includes nextafter regression and reruns all proof'],
    evidence_sha256={str(path.relative_to(a.workspace)).replace('\\','/'):sha(path) for path in (a.verification,qa)},limits=v['limits'])
for path in (a.out/'report.json',repo/'research/drive_resonance_v1_summary.json'):
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(__file__,a.out/'executed_finalize.py');print(json.dumps(dict(result=summary['result'],C_H=519,CTest=51,legacy_WAV=84)))
