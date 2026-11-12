"""Freeze committed full-recipe integration, original players and all attempts."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
s=json.loads((repo/'research/full_recipe_drive_v1_summary.json').read_text(encoding='utf-8'))
assert s['result']=='full_recipe_driver_technical_pass' and s['moving35_complete_recipe_in_driver'] and not s['full_idle_or_acceleration_calibrated']
for name,digest in s['evidence_sha256'].items():assert sha(a.workspace/name)==digest,name
out=a.workspace/'baselines/full_recipe_drive_v1';out.mkdir(exist_ok=False)
shutil.copytree(a.workspace/'references/analysis/full_recipe_drive_v1',out/'evidence')
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('Retained moving35 in the one-controller atlas/native/owned schema8 path.\n'
    'before1 preserves verified schema7 players and a real device take.\n'
    'Original models unchanged; every failed build and exact source is retained.\n'
    'No new timbre/warm-idle/full acceleration/physical7.1.4/longrun acceptance.\n',encoding='utf-8')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,files=files,
    full_idle_or_acceleration_calibrated=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',commit=commit,files=len(files),bytes=sum(v['bytes'] for v in files))))
