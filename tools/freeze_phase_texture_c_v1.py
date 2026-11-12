"""Freeze tested C, listening decisions and native evidence after committing."""
import argparse,json,shutil,subprocess,sys,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
r=json.loads((repo/'research/phase_texture_c_v1_summary.json').read_text(encoding='utf-8'))
assert r['result']=='C_and_short_native_function_pass'
for name,digest in r['source_sha256'].items():assert sha(repo/name)==digest,name
root=a.workspace/'references/analysis/phase_texture_c_v1'
for name,digest in r['binary_sha256'].items():assert sha(repo/'build-phase-texture-c-v1'/name)==digest,name
freeze=a.workspace/'baselines/phase_texture_c_v1';freeze.mkdir(exist_ok=False)
shutil.copytree(root,freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
for name in ('research/phase_texture_c_v1_summary.json','research/phase_texture_v1_acceptance.json',
             'research/共同微扰C接入V1.md','research/听评记录.md','README.md','AGENTS.md',
             'handoff/算法说明.md','handoff/C模块与接口.md','handoff/开发留痕.md',
             'handoff/声纹沉淀与控制边界.md','handoff/研究续接.md','handoff/C文件索引.csv','Launch-Shared-Phase.cmd'):
    target=freeze/'docs'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(freeze/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(freeze/'source.zip') as archive:assert archive.testzip() is None
files=[dict(path=x.relative_to(freeze).as_posix(),bytes=x.stat().st_size,sha256=sha(x))
       for x in sorted(freeze.rglob('*')) if x.is_file()]
(freeze/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,
    offline_light_accepted=True,native_listening_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(freeze/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',files=len(files),commit=commit)))
