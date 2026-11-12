"""Freeze exact monitor sources, logs, device captures and all attempts locally."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
s=json.loads((repo/'research/resonant_monitor_v1_summary.json').read_text(encoding='utf-8'))
assert s['result']=='native_monitor_technical_pass'
for name,digest in s['evidence_sha256'].items():assert sha(a.workspace/name)==digest
out=a.workspace/'baselines/resonant_monitor_v1';out.mkdir(exist_ok=False)
shutil.copytree(a.workspace/'references/analysis/resonant_monitor_v1',out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,
    native_monitor_only=True,driver_take_or_timbre_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',commit=commit,files=len(files),bytes=sum(v['bytes'] for v in files))))
