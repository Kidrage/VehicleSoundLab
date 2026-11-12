"""Publish a full-mixture C result without changing old models or judgments."""
import argparse,csv,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--verification',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

read=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
v=read(a.verification);evidence=a.verification.parent
assert v['result']=='full_C_mixture_and_contracts_pass' and v['Ctests_passed']==49
assert len(v['comparisons'])==9 and len(v['routing'])==3
for name,digest in v['source_sha256'].items():
    assert sha(repo/name)==sha(evidence/'exact_sources'/name)==digest,name
for name,digest in v['input_sha256'].items():assert sha(Path(name))==digest,name
for row in v['comparisons']+v['routing']:assert sha(evidence/row['file'])==row['sha256']
assert sha(evidence/'VslResonantSource_probe.exe')==v['probe_sha256']
for row in v['commands']:
    assert row['exit_code']==row['expected'] and sha(evidence/row['log'])==row['sha256']
proof_path=Path(v['reused_contract_proof']['file']) if 'reused_contract_proof' in v else a.verification
proof=read(proof_path)
if 'reused_contract_proof' in v:assert sha(proof_path)==v['reused_contract_proof']['sha256']
for row in proof['commands']:
    assert sha(proof_path.parent/row['log'])==row['sha256']
    if row['argv'][0] in ('cmake','ctest'):assert row['exit_code']==0
with (evidence/'prior_C_index.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
rows=[v for v in rows if not v['文件'].startswith(('modules/resonant_source/','experiments/resonant_source_v1/'))]
assert len(rows)==492
for row in rows:assert sha(repo/row['文件'])==row['SHA-256']
roles=dict(recipe='非实时原DNA校验及独立谐波功率替换编译，原参数不改',
           voice='DNA/LF持续源与共振纹理同相位，细节预热、独立包络及一次混音',
           output='独立主增益和观察L/R一次前置声床2/12通道路由')
added=[]
for folder in ('modules/resonant_source','experiments/resonant_source_v1'):
    for path in sorted((repo/folder).iterdir()):
        if path.suffix not in ('.c','.h'):continue
        name=path.relative_to(repo).as_posix();added.append(name)
        if folder.startswith('modules/'):
            module,target,role='完整共振声源配方','resonant_source',roles[path.stem]
        else:module,target,role='完整共振声源验证','VslResonantSource_'+path.stem,'独立离线配方导出或契约，不在默认驾驶链'
        rows.append(dict(zip(('文件','模块','构建归属','职责','SHA-256'),(name,module,target,role,sha(path)))))
assert len(added)==8 and len(rows)==500
a.out.mkdir(parents=True,exist_ok=False)
index=repo/'handoff/C文件索引.csv'
with index.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
summary=dict(schema='vsl.resonant-source-summary/1',date='2026-11-12',result='full_C_mixture_parity_only',
    prior_C_H_unchanged=492,new_C_H=8,C_H_rows=500,C_H_index_sha256=sha(index),Ctests=49,
    comparisons=9,comparison_seconds_each=8,output_routes=3,
    maximum_errors={key:max(row['errors'][key] for row in v['comparisons']) for key in v['predeclared_limits']},
    maximum_phase_error_cycles=max(row['source_phase_error_cycles'] for row in v['comparisons']),
    maximum_peak_FS=max(row['peak_FS'] for row in v['comparisons']),
    prepared_model_compiled_in_C=True,detail_uses_source_phase=True,only_detail_prewarmed=True,
    no_new_fitting_or_room_or_PCM=True,source_2_12_exact=True,other10channels_zero=True,
    native_driver_take_or_default_integrated=False,new_listening_acceptance=False,
    listening=dict(moving35='held existing offline recipe; no new moving audition',idle='pending original question'),
    preserved_attempts=['verify1 passed49tests/3moving cases then wrong idle archive prefix failed','verify2 fixed evidence path only and reused exact build/test proof'],
    evidence_sha256={str(path.relative_to(a.workspace)).replace('\\','/'):sha(path) for path in {proof_path,a.verification}},
    limits=v['limits'])
for path in (a.out/'report.json',repo/'research/resonant_source_v1_summary.json'):
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(__file__,a.out/'executed_finalize.py')
print(json.dumps(dict(result=summary['result'],C_H=500,Ctests=49,errors=summary['maximum_errors'])))
