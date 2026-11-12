"""Build isolated variable-density C kernels and preserve every command/source."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--build',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
args.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),repo/'research/residual_dense_v1_plan.json',
    *[p for name in ('modules/residual_dense','modules/sound_residual','experiments/residual_dense_v1') for p in (repo/name).glob('*') if p.is_file()],
    *[repo/name for name in ('src/io/wav.c','src/io/wav.h','src/io/file.c','src/io/file.h')]]
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.residual-dense-build/1',result='running',commands=[],
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip())
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
try:
    index=args.workspace/'baselines/line_density_v1/docs/C文件索引.csv'
    with index.open(encoding='utf-8-sig',newline='') as stream:old=list(csv.DictReader(stream))
    assert len(old)==436
    for row in old:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    report['prior_c_index_sha256']=sha(index);report['prior436_C_sources_unchanged']=True
    commands=[['cmake','-S',str(repo/'experiments/residual_dense_v1'),'-B',str(args.build),'-G','Visual Studio 17 2022','-A','x64'],
        ['cmake','--build',str(args.build),'--config','Release','--parallel'],
        ['ctest','--test-dir',str(args.build),'-C','Release','--output-on-failure'],
        ['ctest','--test-dir',str(repo/'handoff-build'),'-C','Release','--output-on-failure']]
    for i,command in enumerate(commands):
        completed=subprocess.run(command,cwd=repo,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
        log=args.out/f'command_{i}.log';log.write_text(completed.stdout+completed.stderr,encoding='utf-8',newline='\n')
        report['commands'].append(dict(command=command,exit_code=completed.returncode,log_sha256=sha(log)))
        print(json.dumps(dict(command=i,exit_code=completed.returncode,tail=(completed.stdout+completed.stderr)[-1500:])),flush=True)
        completed.check_returncode()
    binaries=[args.build/'Release/residual_dense_probe.exe',args.build/'Release/residual_dense_checks.exe']
    report.update(result='pass',binaries={str(p):sha(p) for p in binaries},default_driver_rebuilt=False)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=report['result'],binaries=report.get('binaries'))),flush=True)
