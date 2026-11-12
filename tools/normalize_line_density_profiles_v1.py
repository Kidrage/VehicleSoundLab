"""Preserve raw CRLF exports; qualify canonical Git copies through the C reader."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

summary_path=repo/'research/line_density_v1_summary.json'
summary=json.loads(summary_path.read_text(encoding='utf-8'))
for name,digest in summary['current_source_sha256'].items():assert sha(repo/name)==digest,name
root=args.workspace/'references/analysis/line_density_v1'
out=args.out;out.mkdir(exist_ok=False)
shutil.copy2(summary_path,out/'summary_before_publication.json')
index_path=repo/'voices/line_density_v1/index.json'
shutil.copy2(index_path,out/'index_before_publication.json')
for name in ('tools/finalize_line_density_v1.py','tools/normalize_line_density_profiles_v1.py'):
    target=out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
check=subprocess.run(['git','diff','--cached','--check'],cwd=repo,capture_output=True,text=True)
assert check.returncode!=0 and 'trailing whitespace' in check.stdout
(out/'staged_whitespace_failure.txt').write_text(check.stdout+check.stderr,encoding='utf-8',newline='\n')
probe=repo/'handoff-build/bin/Release/VslResidual_probe.exe'
index=json.loads(index_path.read_text(encoding='utf-8'));rows=[]
for entry,original in zip(index['entries'],summary['authored_experimental_profiles']):
    path=repo/entry['residual'];before=path.read_bytes();assert sha(path)==original['residual_sha256']
    assert b'\r\n' in before and before.replace(b'\r\n',b'').find(b'\n')==-1
    original_path=out/('original_'+path.name);original_path.write_bytes(before)
    after=before.replace(b'\r\n',b'\n');assert before.decode('ascii').split()==after.decode('ascii').split()
    path.write_bytes(after)
    amount=round(entry['amount']*100);audio_path=out/f'normalized_{amount}_cloud.wav'
    command=[str(probe),str(path),str(audio_path),'.1','1','1','8121907']
    process=subprocess.run(command,capture_output=True,text=True,timeout=30);process.check_returncode()
    audio,rate=sf.read(audio_path,always_2d=True)
    frozen,frozen_rate=sf.read(root/'render1/raw'/f'density_{amount}_8121907_cloud.wav',always_2d=True)
    assert rate==frozen_rate==48000 and len(audio)==4800 and np.array_equal(audio,frozen[:len(audio)])
    entry['residual_sha256']=sha(path);original['residual_sha256']=sha(path)
    rows.append(dict(amount=entry['amount'],raw_sha256=sha(original_path),published_sha256=sha(path),
        token_sequence_exact=True,C_decoded_samples_exact=True,checked_frames=len(audio),command=command,
        probe_sha256=sha(probe),stdout=process.stdout,stderr=process.stderr))
index_path.write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
report=dict(schema='vsl.line-density-publication/1',result='pass',reason='CRLF counted as trailing whitespace under repository -text attributes; original exports retained',
    profiles=rows,summary_before_sha256=sha(out/'summary_before_publication.json'),
    exact_source_sha256={name:sha(out/'exact_sources'/name) for name in ('tools/finalize_line_density_v1.py','tools/normalize_line_density_profiles_v1.py')})
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
summary['publication_normalization']=dict(report='publication1/report.json',report_sha256=sha(out/'report.json'),
    original_exports_preserved=True,token_sequences_exact=True,C_decoded_samples_exact=True)
summary['current_source_sha256']['tools/normalize_line_density_profiles_v1.py']=sha(Path(__file__))
summary['evidence_sha256']={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
summary['publication_normalization']['report']=(out/'report.json').relative_to(root).as_posix()
summary['limits'].append('Git residual copies have canonical LF; publication1 preserves the pre-mutation exit-code assertion failure; publication2 retains raw CRLF copies/pre-publication summary/index and exact normalized C-reader sample parity')
summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result='pass',profiles=len(rows),C_samples_exact=True,raw_exports_unchanged=True)),flush=True)
