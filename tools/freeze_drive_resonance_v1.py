"""Freeze runnable driver/player versions and all attempts without external media copies."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
s=json.loads((repo/'research/drive_resonance_v1_summary.json').read_text(encoding='utf-8'));assert s['result']=='optional_driving_detail_technical_pass'
for name,digest in s['evidence_sha256'].items():assert sha(a.workspace/name)==digest
out=a.workspace/'baselines/drive_resonance_v1';out.mkdir(exist_ok=False)
shutil.copytree(a.workspace/'references/analysis/drive_resonance_v1',out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('Optional driving continuous detail\n'
    'Current schema6 player/UI: evidence/verify4/bin/\n'
    'Preserved schema5 player: evidence/before1/VslAtlasTake_render.exe\n'
    'Both take files own their models. UI needs the project voices directory.\n'
    'All attempts and exact executed sources are preserved. No new listening acceptance.\n',encoding='utf-8')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,
    optional_driving_detail_only=True,full_state_timbre_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',commit=commit,files=len(files),bytes=sum(v['bytes'] for v in files))))
