"""Finalize the independent startup candidate, or freeze its committed handoff."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--freeze',action='store_true');a=p.parse_args()
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
root=a.workspace/'references/analysis/startup_texture_v1'
summary_path=repo/'research/startup_texture_v1_summary.json'
docs=['research/启动机械纹理V1.md','research/startup_texture_v1_summary.json',
      'handoff/研究续接.md','handoff/开发留痕.md','handoff/C模块与接口.md',
      'handoff/C文件索引.csv','modules/start_texture/README.md','AGENTS.md']
if a.freeze:
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    summary=json.loads(summary_path.read_text(encoding='utf-8'))
    for name,digest in summary['current_source_sha256'].items():assert sha(repo/name)==digest,name
    for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
    out=a.workspace/'baselines/startup_texture_v1';out.mkdir(exist_ok=False)
    shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
    for name in docs:
        target=out/'docs'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
    with zipfile.ZipFile(out/'source.zip') as z:assert z.testzip() is None
    files=[dict(path=x.relative_to(out).as_posix(),bytes=x.stat().st_size,sha256=sha(x))
           for x in sorted(out.rglob('*')) if x.is_file()]
    (out/'manifest.json').write_text(json.dumps(dict(schema='vsl.startup-texture-freeze/1',source_commit=revision,
        human_accepted=False,current_UI_integrated=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for row in files:assert sha(out/row['path'])==row['sha256']
    print(json.dumps(dict(commit=revision,files=len(files),bytes=sum(x['bytes'] for x in files))))
    sys.exit(0)

assert not summary_path.exists()
proof=json.loads((root/'verification4/report.json').read_text(encoding='utf-8'))
review=json.loads((root/'review1/report.json').read_text(encoding='utf-8'))
analysis=json.loads((root/'analysis1/report.json').read_text(encoding='utf-8'))
assert proof['result']=='isolated_candidate_verified' and review['result']=='pass' and analysis['result']=='observed_only'
for name,digest in proof['source_sha256'].items():assert sha(repo/name)==digest,name
assert sha(repo/'tools/analyze_startup_layers_v1.py')==analysis['source_sha256']
assert sha(repo/'tools/review_startup_texture_v1.py')==review['source_sha256']
index=repo/'handoff/C文件索引.csv'
with index.open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
assert len(old)==448
spec=importlib.util.spec_from_file_location('startup_index',repo/'handoff/tools/index_sources.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rows=list(m.code_rows());mapping={row[0]:row for row in rows};assert len(rows)==454
for row in old:assert tuple(row.values())==mapping[row['文件']],row['文件']
with index.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.writer(f,lineterminator='\n');writer.writerow(old[0].keys());writer.writerows(rows)
dest=repo/'voices/start_texture_v1';dest.mkdir(exist_ok=False)
shutil.copy2(root/'verification4/A_cabin_early.start',dest/'A cabin early.start')
(dest/'README.md').write_text('''# 启动前段纹理候选

仅供独立 `start_texture_probe` 使用，不在驾驶UI默认模型库。A车内36.65–37.12秒，300–8000Hz总观察谱矩；不是已分离起动机或完整启动。`A cabin early.start` 不含PCM或时间轨迹，16带／每带32组共享与独立载波；形状静态，工程淡化5／35ms。音色待听评。

见 [研究记录](../../research/启动机械纹理V1.md) 与 `modules/start_texture/README.md`。
''',encoding='utf-8')
accepted=json.loads((repo/'research/stereo_bed_v1_summary.json').read_text(encoding='utf-8'))['accepted_models_unchanged']
for name,digest in accepted.items():assert sha(repo/name)==digest,name
max_power=max(abs(v) for seed in proof['held_moments'] for row in seed['errors'] for v in row['power_dB'])
max_coherence=max(row['coherence_error'] for seed in proof['held_moments'] for row in seed['errors'])
new_paths=[row[0] for row in rows if row[0] not in {r['文件'] for r in old}]
current={**proof['source_sha256'],'handoff/C文件索引.csv':sha(index),
         'handoff/tools/index_sources.py':sha(repo/'handoff/tools/index_sources.py'),
         'tools/review_startup_texture_v1.py':sha(repo/'tools/review_startup_texture_v1.py'),
         'tools/finish_startup_texture_v1.py':sha(__file__),
         'voices/start_texture_v1/A cabin early.start':sha(dest/'A cabin early.start')}
summary=dict(schema='vsl.startup-texture-summary/1',date='2026-11-12',result='independent_early_layer_candidate',
    C_H_count=454,new_C_H=new_paths,prior_C_H_unchanged=448,c_index_sha256=sha(index),
    standalone_ctests=24,existing_driver_trace_equal=proof['driver_trace_equal_old_new_all_seeds'],
    raw_source_gate_independent=proof['raw_source_identical_across_gates'],profile=proof['profile'],
    model_path='voices/start_texture_v1/A cabin early.start',
    max_training_band_error_dB=max_power,max_training_complex_coherence_error=max_coherence,
    max_training_half_difference_dB=max(abs(v) for row in proof['training_half_power_difference_dB'] for v in row),
    page=review['page'],clips=review['clips'],upstream=proof['upstream'],
    human_accepted=False,current_UI_integrated=False,whole_startup_restored=False,
    accepted_models_unchanged=accepted,limitations=proof['limits'],
    current_source_sha256=current,
    evidence_sha256={path.relative_to(root).as_posix():sha(path) for path in sorted(root.rglob('*'))
                     if path.is_file() and '__pycache__' not in path.parts})
summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=summary['result'],C_H=454,old_unchanged=448,new=len(new_paths),ctests=24,page=review['page']),ensure_ascii=True))
