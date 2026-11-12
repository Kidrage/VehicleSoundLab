"""Archive the committed candidate, all attempts and the source inspection evidence."""
import argparse,json,shutil,subprocess,sys,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
s=json.loads((repo/'research/stereo_resonance_v1_summary.json').read_text(encoding='utf-8'))
assert s['result']=='stereo_candidate_technical_pass' and not s['listening_accepted']
assert sha(repo/s['profile_path'])==s['profile_sha256']
for name,digest in s['evidence_sha256'].items():assert sha(a.workspace/name)==digest,name
v=json.loads((a.workspace/'references/analysis/stereo_resonance_v1/verify1/report.json').read_text(encoding='utf-8'))
for name,digest in v['evidence_sha256'].items():assert sha(a.workspace/'references/analysis/stereo_resonance_v1/verify1'/name)==digest,name
out=a.workspace/'baselines/stereo_resonance_v1';out.mkdir(exist_ok=False)
shutil.copytree(a.workspace/'references/analysis/stereo_resonance_v1',out/'evidence')
shutil.copytree(a.workspace/'references/analysis/idle_target_v2',out/'source_inspection')
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as z:assert z.testzip() is None
(out/'README.txt').write_text('Stereo continuous detail candidate: A startup-settling cabin\n'
    'evidence/fit1 and fit2 preserve the parameter fitting versions (profiles byte equal).\n'
    'evidence/verify1 includes executed sources, binaries, known controls, 52 CTests and three48s C renders.\n'
    'evidence/review1/index.html is the single-player dry comparison.\n'
    'source_inspection preserves E stationary staging-to-launch frames, excluded as idle.\n'
    '600..850Hz gap remains; no warm-idle/acceleration/load/driver/native/take/7.1.4 or listening acceptance.\n',encoding='utf-8')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,listening_accepted=False,
    full_idle_or_acceleration_calibrated=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',commit=commit,files=len(files),bytes=sum(v['bytes'] for v in files))))
