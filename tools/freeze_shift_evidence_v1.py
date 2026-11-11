"""Freeze the offline study, including failures and hash-matched source versions."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'], cwd=repo).strip()
summary_path = repo / 'research/shift_evidence_v1_summary.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
assert summary['result'] == 'pass' and not summary['runtime_changes']
evidence = args.workspace / 'references/analysis/shift_evidence_v1'
assert str(evidence) == summary['evidence_root']
for name, expected in summary['source_sha256'].items():
    assert sha(repo / name) == expected, name
for name, expected in summary['evidence_sha256'].items():
    assert sha(evidence / name) == expected, name
revision = subprocess.check_output(['git','rev-parse','HEAD'], cwd=repo, text=True).strip()
out = args.workspace / 'baselines/shift_evidence_v1'
out.mkdir(exist_ok=False)
shutil.copytree(evidence, out/'evidence', ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/换挡时序与声纹V1.md','research/shift_evidence_v1_summary.json',
             'research/drive_evidence_v1_annotations.json','references/segments_v1.json'):
    shutil.copy2(repo/name, out/'docs'/Path(name).name)
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision], cwd=repo, check=True)
with zipfile.ZipFile(out/'source.zip') as archive:
    assert archive.testzip() is None
(out/'README.txt').write_text('换挡时序与声纹V1，离线研究，无新增运行音色。\n提交：'+revision+'\n'
    '最终依据为evidence/attempt4；前三次迭代、失败与逐版源码均保留。\n'
    '重新分析需恢复原交接Release的E批准素材／float主文件，参照docs中的provenance和SHA。\n'
    '未改C、UI、驾驶参数或认可DNA／低频；数值通过不表示换挡音色听评通过。\n', encoding='utf-8')
files = [dict(path=p.relative_to(out).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.shift-evidence-freeze/1',
    source_commit=revision, human_accepted=False, runtime_changes=False, files=files),
    ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
for row in files:
    assert sha(out/row['path']) == row['sha256']
print(json.dumps(dict(path=str(out), commit=revision, files=len(files),
    bytes=sum(r['bytes'] for r in files)), ensure_ascii=False))
