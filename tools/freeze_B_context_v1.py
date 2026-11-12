"""Freeze all successful/rejected B evidence and committed source without refitting."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=json.loads((repo/'research/B_context_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result']=='source_context_corrected_no_new_timbre'
assert not summary['new_DNA_exported'] and not summary['idle_or_acceleration_timbre_complete']
publication=a.workspace/'references/analysis/cabin_low_context_v1/final1'
assert sha(publication/'report.json')==summary['publication_report_sha256']
for name,digest in summary['evidence_sha256'].items():assert sha(a.workspace/name)==digest,name
for name,digest in summary['source_sha256'].items():assert sha(publication/'exact_sources'/name)==digest,name
assert sha(a.workspace/'references/segments_v1.json')==sha(repo/'references/segments_v1.json')
out=a.workspace/'baselines/cabin_low_context_v1';out.mkdir(exist_ok=False)
shutil.copytree(a.workspace/'references/analysis/cabin_low_context_v1',out/'context_evidence')
shutil.copytree(a.workspace/'references/analysis/cabin_low_v1',out/'acoustic_evidence')
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),commit],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:assert archive.testzip() is None
(out/'README.txt').write_text(
    'Approved B context recovery and source-state correction, not new timbre acceptance.\n'
    'All download/import/decode failures and phase rejections are retained.\n'
    'New encoded context video and paired audio are inside context_evidence; prior raw MP3/master remain unchanged in the main media archive.\n'
    '100 B frames and13 E frames, all contact sheets and exact executed analysis sources are retained.\n'
    'Committed source.zip contains final authored documentation; publication exact_sources retain the exact earlier publication bytes.\n'
    '530 C/H and prior voices unchanged; no repeat of53existing CTests or new device/listening qualification.\n'
    'Moving35 preserved; exterior idle, middle/low loaded acceleration and same-RPM load coverage remain incomplete.\n',encoding='utf-8')
files=[dict(path=file.relative_to(out).as_posix(),bytes=file.stat().st_size,sha256=sha(file))
    for file in sorted(out.rglob('*')) if file.is_file()]
manifest=dict(schema='vsl.freeze/1',source_commit=commit,files=files,
    goal_complete=False,new_timbre_accepted=False)
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for item in files:assert sha(out/item['path'])==item['sha256']
print(json.dumps(dict(result='frozen',commit=commit,files=len(files),bytes=sum(v['bytes'] for v in files))),flush=True)
