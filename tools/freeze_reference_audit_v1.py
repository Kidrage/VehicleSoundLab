"""Freeze text-route and stereo observations with failed attempts and exact sources."""
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
        return hashlib.file_digest(stream,'sha256').hexdigest()


assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary = json.loads((repo/'research/reference_audit_v1_summary.json').read_text(encoding='utf-8'))
assert summary['result'] == 'pass' and not summary['runtime_changes'] and not summary['human_accepted']
assert summary['stereo']['promotion_decision'] == 'not_promoted'
for name,digest in summary['source_sha256'].items():
    assert sha(repo/name) == digest, name
for name,root in summary['evidence_roots'].items():
    assert Path(root) == args.workspace/'references/analysis'/name
    for relative,digest in summary['evidence_sha256'][name].items():
        assert sha(Path(root)/relative) == digest, (name,relative)
for name,digest in summary['input_metadata_sha256'].items():
    assert sha(args.workspace/name) == digest
assert sha(repo/'handoff/C文件索引.csv') == summary['c_index_sha256']
assert sha(args.workspace/'baselines/numeric_scope_v1/manifest.json') == summary['prior_manifest_sha256']
out = args.workspace/'baselines/reference_audit_v1'
out.mkdir(exist_ok=False)
for name,root in summary['evidence_roots'].items():
    shutil.copytree(root,out/'evidence'/name,ignore=shutil.ignore_patterns('__pycache__'))
for name in summary['input_metadata_sha256']:
    target = out/'input_metadata'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(args.workspace/name,target)
(out/'docs').mkdir()
for name in ('research/V6公开链路核查V1.md','research/立体声相位斜率V1.md',
    'research/reference_audit_v1_summary.json','research/stereo_delay_v1_plan.json',
    'handoff/研究续接.md','handoff/C模块与接口.md','handoff/C文件索引.csv','AGENTS.md'):
    shutil.copy2(repo/name,out/'docs'/Path(name).name)
revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(out/'source.zip') as archive:
    assert archive.testzip() is None
(out/'README.txt').write_text('V6公开链路与立体声相位斜率，提交：'+revision+'\n'
    '上游固定revision的129个文本文件，无新音视频。保留fetch1超时、恢复fetch2和实际执行脚本。\n'
    'V10/V12公开DNA与启动采样分支分别核对；静态连线验证不是Max默认可听行为验证。\n'
    '六段原始stereo混合录音、12组合成控制、直接DFT及独立指标算式通过；48频带仅E一个通过预测门槛。\n'
    '不推广延迟方案，无C/H、模型、状态、UI变化或新听评认可。436份C/H和已认可DNA/LF原值保留。\n'
    '原始素材按既有provenance SHA恢复。继续分开录音L/R传递与未来7.1.4物理对象。\n',encoding='utf-8')
files = [dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
         for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.reference-audit-freeze/1',
    source_commit=revision,runtime_changes=False,human_accepted=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for row in files:
    assert sha(out/row['path']) == row['sha256']
print(json.dumps(dict(path=str(out),commit=revision,files=len(files),bytes=sum(r['bytes'] for r in files))))
