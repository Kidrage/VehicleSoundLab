"""Freeze new diagnostic evidence/decisions without rewriting prior baselines."""
import argparse,json,shutil,subprocess,sys,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
r=json.loads((repo/'research/dna_texture_v2_summary.json').read_text(encoding='utf-8'))
assert r['result']=='diagnostics_pass' and r['C_H_unchanged']==478
for name,digest in r['source_sha256'].items():assert sha(repo/name)==digest,name
for name,digest in r['input_sha256'].items():assert sha(Path(name))==digest,name
freeze=a.workspace/'baselines/dna_texture_v2';freeze.mkdir(exist_ok=False)
for name in ('dna_texture_v2','phase_texture_parity_v1'):
    shutil.copytree(a.workspace/'references/analysis'/name,freeze/'evidence'/name,
                    ignore=shutil.ignore_patterns('__pycache__'))
for name in ('research/DNA高频质感诊断与优化V2.md','research/dna_texture_v2_summary.json',
             'research/dna_texture_v2_plan.json','research/phase_texture_c_v1_listening.json',
             'research/phase_texture_v1_followup.json','research/phase_texture_v1_acceptance.json',
             'README.md','AGENTS.md','handoff/算法说明.md','handoff/开发留痕.md',
             'handoff/研究续接.md','handoff/C文件索引.csv'):
    dest=freeze/'docs'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(freeze/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(freeze/'source.zip') as z:assert z.testzip() is None
files=[dict(path=p.relative_to(freeze).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(freeze.rglob('*')) if p.is_file()]
(freeze/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,
    new_timbre_accepted=False,new_C_H=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(freeze/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',files=len(files),commit=commit)))
