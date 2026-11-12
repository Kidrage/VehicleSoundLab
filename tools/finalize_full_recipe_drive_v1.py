"""Bind exact successful build/device proof and refresh engineering handoff."""
import argparse,csv,hashlib,json,shutil
from pathlib import Path
from full_recipe_diagram_v1 import draw
p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','verification','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
v=json.loads((a.verification/'report.json').read_text(encoding='utf-8'))
assert v['result']=='full_recipe_driver_technical_pass' and v['Ctests_passed']==55
for name,digest in v['sources'].items():assert sha(repo/name)==digest,name
for name,digest in v['evidence_sha256'].items():assert sha(a.verification/name)==digest,name
for name,digest in v['unchanged_voices'].items():assert sha(repo/name)==digest,name
index=repo/'handoff/C文件索引.csv'
with index.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
assert len(rows)==530;keys=list(rows[0]);assert len(keys)==5
roles={
    'modules/drive_recipe/bank':'局部完整配方拥有低频参数、支持界限与编译功率mask，非实时事务校验',
    'modules/drive_recipe/shape':'依实际下一采样根音与细节量计算耦合功率替换，无独立时钟',
    'modules/drive_recipe/voice':'原DNA相位及锚点原点驱动独立相干LF，连续统计与独立量',
    'experiments/full_recipe_drive_v1/models':'非实时加载原冻结行驶35%配方，不改拟合参数',
    'experiments/full_recipe_drive_v1/kernel_checks':'三seed原完整配方oracle、合成双锚点、同相位与静音推进契约',
    'experiments/full_recipe_drive_v1/checks':'统一驾驶零路径／越界恢复／独立LF／拥有schema8与2-12契约'}
for row in rows:
    row['SHA-256']=sha(repo/row['文件'])
    if row['文件']=='modules/atlas_take_io/codec.c':row[keys[3]]='schema8显式参数IO，拥有独立LF与功率mask，严格版本身份'
for name in v['new_C_H']:
    stem=str(Path(name).with_suffix('')).replace('\\','/');role=roles[stem]
    module='完整配方驾驶适配' if name.startswith('modules/') else '完整配方实验／契约'
    target='drive_recipe' if name.startswith('modules/') else 'full_recipe_models' if '/models.' in name else 'VslFullRecipeKernel_checks' if '/kernel_checks.' in name else 'VslFullRecipeDrive_checks'
    rows.append(dict(zip(keys,(name,module,target,role,sha(repo/name)))))
assert len(rows)==540 and len(v['modified_prior_C_H'])==24 and len(v['new_C_H'])==10
assert len(set(row['文件'] for row in rows))==540
with index.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows(rows)
summary={key:value for key,value in v.items() if key not in ('evidence_sha256','sources','commands','unchanged_voices')}
summary.update(schema='vsl.full-recipe-drive-summary/1',date='2026-11-13',C_H_rows=540,unchanged_prior_C_H=506,
    modified_prior_C_H=v['modified_prior_C_H'],new_C_H=v['new_C_H'],C_H_index_sha256=sha(index),
    moving35_complete_recipe_in_driver=True,source_profiles_unchanged=True,
    evidence_sha256={(a.verification/'report.json').relative_to(a.workspace).as_posix():sha(a.verification/'report.json')})
for path in (repo/'research/full_recipe_drive_v1_summary.json',a.out/'summary.json'):
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copy2(__file__,a.out/'executed_finalize.py');shutil.copy2(repo/'tools/full_recipe_diagram_v1.py',a.out/'executed_diagram.py')
draw(repo/'handoff')
print(json.dumps(dict(result=summary['result'],C_H=540,Ctests=55,modified=24,new=10)))
