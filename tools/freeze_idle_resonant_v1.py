"""Freeze context, failed eligibility, actual candidates and exact code together."""
import argparse,json,shutil,subprocess,sys,zipfile
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha

assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=json.loads((repo/'research/idle_resonant_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='offline_candidate_technical_pass_only'
assert sha(repo/summary['profile_file'])==summary['profile_sha256']
for name,digest in summary['evidence_sha256'].items():assert sha(a.workspace/name)==digest,name
assert sha(repo/'voices/resonant_detail_v1/SELECTION.json')==summary['moving_selection_sha256']
freeze=a.workspace/'baselines/idle_resonant_v1';freeze.mkdir(exist_ok=False)
for folder in ('idle_context_v1','idle_resonant_v1'):
    shutil.copytree(a.workspace/'references/analysis'/folder,freeze/'evidence'/folder,
        ignore=shutil.ignore_patterns('__pycache__'))
(freeze/'bin').mkdir();probe=repo/'build-phase-texture-c-v1/bin/Release/VslSoundDna_probe.exe'
shutil.copy2(probe,freeze/'bin'/probe.name)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(freeze/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(freeze/'source.zip') as archive:assert archive.testzip() is None
files=[dict(path=p.relative_to(freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
    for p in sorted(freeze.rglob('*')) if p.is_file()]
(freeze/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,
    human_accepted=False,new_C_H=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(freeze/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(v['bytes'] for v in files),commit=commit)))
