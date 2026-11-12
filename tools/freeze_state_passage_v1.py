"""Freeze state-passage sources, all attempts and published listening bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
summary = json.loads((repo/'research/state_passage_v1_summary.json').read_text(encoding='utf-8'))
root = args.workspace/'references/analysis/state_passage_v1'
for name, digest in summary['current_source_sha256'].items():
    assert sha(repo/name) == digest, name
for name, digest in summary['input_sha256'].items():
    assert sha(name) == digest, name
for name, digest in summary['evidence_sha256'].items():
    assert sha(root/name) == digest, name
assert sha(repo/'handoff/C文件索引.csv') == summary['c_index_sha256']
out = args.workspace/'baselines/state_passage_v1'
out.mkdir(exist_ok=False)
shutil.copytree(root, out/'evidence', ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/驻车状态局部对照V1.md', 'research/state_passage_v1_summary.json',
             'handoff/C模块与接口.md', 'handoff/研究续接.md', 'handoff/C文件索引.csv', 'AGENTS.md'):
    shutil.copy2(repo/name, out/'docs'/Path(name).name)
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
subprocess.run(['git', 'archive', '--format=zip', '--output='+str(out/'source.zip'), revision], cwd=repo, check=True)
with zipfile.ZipFile(out/'source.zip') as archive:
    assert archive.testzip() is None
files = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.state-passage-freeze/1', source_commit=revision,
    source_only=True, prior442_C_H_unchanged=True, human_accepted=False, files=files), ensure_ascii=False, indent=2)+'\n',
    encoding='utf-8', newline='\n')
for row in files:
    assert sha(out/row['path']) == row['sha256']
print(json.dumps(dict(path=str(out), commit=revision, files=len(files), bytes=sum(row['bytes'] for row in files))))
