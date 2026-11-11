"""Freeze the qualified numeric scope and retain its failed frame0 fixture."""
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


assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary = json.loads((repo/'research/numeric_scope_v1_summary.json').read_text(encoding='utf-8'))
assert summary['technical_validation'] == 'pass' and not summary['hard_realtime_qualified']
root = args.workspace/'references/analysis/numeric_scope_v1'
assert str(root) == summary['evidence_root']
for name,digest in summary['source_sha256'].items():
    assert sha(repo/name) == digest, name
for name,digest in summary['evidence_sha256'].items():
    assert sha(root/name) == digest, name
out = args.workspace/'baselines/numeric_scope_v1'
out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
(out/'docs').mkdir()
for name in ('research/数值作用域V1.md','research/numeric_scope_v1_summary.json',
    'handoff/C模块与接口.md','handoff/研究续接.md','handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:
    assert archive.testzip() is None
(out/'README.txt').write_text('数值作用域V1，提交：'+revision+'\n'
    'x64新DNA驾驶／监听内局部FTZ/DAZ；完整调用线程MXCSR恢复，支持嵌套及错误返回。\n'
    '40项CTest、6场景156音轨、固定DNA字节、旧行程身份、静音设备与新行程2/12通道重合成通过。\n'
    '驾驶分轨最大差异约1.18e-38满幅；不能声称所有音轨字节一致。\n'
    '三次交替离线A/E耗时中位数降低9.30%/14.55%，A仍超时；非硬实时或新音色认可。\n'
    '保留verification1遗漏第0帧事件的夹具／二进制／错误，及修正后的verification2。\n'
    '旧行程继续使用对应冻结播放器，不降低身份校验。\n',encoding='utf-8')
files = [dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.numeric-scope-freeze/1',
    source_commit=revision,technical_validation='pass',hard_realtime_qualified=False,
    files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:
    assert sha(out/row['path']) == row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(r['bytes'] for r in files))))
