"""Freeze clean committed integration and every local attempt/inspection."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
s=json.loads((repo/'research/stereo_drive_v1_summary.json').read_text(encoding='utf-8'))
assert s['result']=='stereo_driver_technical_pass' and not s['full_idle_or_acceleration_calibrated']
for name,digest in s['evidence_sha256'].items():assert sha(a.workspace/name)==digest,name
out=a.workspace/'baselines/stereo_drive_v1';out.mkdir(exist_ok=False)
for name,folder in (('evidence','stereo_drive_v1'),('stereo_diagnostic','stereo_joint_v1'),('dyno_inspection','dyno_tail_v1')):
    shutil.copytree(a.workspace/'references/analysis'/folder,out/name)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text('One-driver stereo detail adapter / native study / owned schema7,28controls.\n'
    'before1 contains schema6 binaries and a real owned device take.\n'
    'Every failed verification/build remains under evidence. Source inspection and rejected lossless diagnostic retained.\n'
    'No new sound fit, warm-idle/load calibration or listening/physical7.1.4 acceptance.\n',encoding='utf-8')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.freeze/1',source_commit=commit,files=files,
    full_idle_or_acceleration_calibrated=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:assert sha(out/row['path'])==row['sha256']
print(json.dumps(dict(result='frozen',commit=commit,files=len(files),bytes=sum(v['bytes'] for v in files))))
