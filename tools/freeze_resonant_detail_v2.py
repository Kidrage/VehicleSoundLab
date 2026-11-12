"""Freeze this feedback and the paired candidate without altering v1 evidence."""
import argparse,json,shutil,subprocess,sys,zipfile
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=json.loads((repo/'research/resonant_detail_v2_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='offline_candidate_technical_pass_only' and summary['prior70']=='rejected'
assert summary['candidate_listening']=='prior35_preferred_v2_not_adopted'
assert sha(repo/summary['latest_feedback_file'])==summary['latest_feedback_sha256']
assert sha(repo/summary['profile_file'])==summary['profile_sha256']
root=a.workspace/'references/analysis/resonant_detail_v2'
for name,digest in summary['evidence_sha256'].items():assert sha(root/name)==digest,name
for folder in ('fit1','render1'):
    report=json.loads((root/folder/'report.json').read_text(encoding='utf-8'))
    for name,digest in report['source_sha256'].items():assert sha(repo/name)==digest,name
freeze=a.workspace/'baselines/resonant_detail_v2';freeze.mkdir(exist_ok=False)
shutil.copytree(root,freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
probe=repo/'build-phase-texture-c-v1/bin/Release/VslSoundDna_probe.exe'
(freeze/'bin').mkdir();shutil.copy2(probe,freeze/'bin'/probe.name)
for name in ('research/共振细节中频保护V2.md','research/resonant_detail_v2_plan.json',
             'research/resonant_detail_v2_summary.json','research/resonant_detail_v1_listening.json',
             'research/resonant_detail_v2_listening.json','research/怠速与加速完成度V1.md',
             'research/听评记录.md','AGENTS.md','handoff/算法说明.md','handoff/开发留痕.md',
             'handoff/研究续接.md','handoff/C文件索引.csv',
             'voices/resonant_detail_v2/detail.json','voices/resonant_detail_v2/README.md'):
    target=freeze/'docs'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(freeze/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(freeze/'source.zip') as archive:assert archive.testzip() is None
files=[dict(path=p.relative_to(freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
       for p in sorted(freeze.rglob('*')) if p.is_file()]
(freeze/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,
    prior35='held_moving_offline_reference',prior70='rejected',new_candidate_listening='not_adopted',new_C_H=False,files=files),
    ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(freeze/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(x['bytes'] for x in files),commit=commit)))
