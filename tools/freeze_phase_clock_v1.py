"""Freeze an explicitly unpromoted phase-clock study and its complete ledger."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
summary=repo/'research/phase_clock_v1_summary.json';r=json.loads(summary.read_text(encoding='utf-8'))
assert r['combined_validation']=='not_passed' and not r['runtime_changed'] and not r['new_model_promoted']
root=Path(r['evidence_root'])
for p,h in r['source_sha256'].items():assert sha(repo/p)==h,p
for p,h in r['evidence_sha256'].items():assert sha(root/p)==h,p
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
out=args.workspace/'baselines/phase_clock_v1';out.mkdir(exist_ok=False)
shutil.copytree(root,out/'evidence');(out/'docs').mkdir()
(out/'inputs').mkdir()
clock=args.workspace/'references/analysis/state_colour_v2/clocks_attempt2/report.json'
original=json.loads((root/'attempt3/report.json').read_text(encoding='utf-8'))
assert sha(clock)==original['clocks_sha256']
shutil.copy2(clock,out/'inputs/original_clocks_report.json')
old=args.workspace/'baselines/state_colour_v2/evidence/colour_attempt1/source/tools/state_dna_v1/compare.py'
shutil.copy2(old,out/'inputs/frozen_compare.py')
shutil.copy2(args.workspace/'references/segments_v1.json',out/'inputs/segments_v1.json')
for p in (summary,repo/'research/离线时钟校验V1.md',repo/'tools/phase_clock_v1/README.md'):
    shutil.copy2(p,out/'docs'/p.name)
subprocess.run(['git','archive','--format=zip','--output='+str(out/'source.zip'),revision],cwd=repo,check=True)
(out/'README.txt').write_text('离线时钟校验V1\n提交：'+revision+'\n联合验证未通过，没有推广新模型或修改实时C。\n'
    '16组新控制通过；原最难反例约1.007dB；真实A完整起落配对尚未通过独立一致性条件。\n'
    'evidence/comparison.png汇总不同范围，所有版本源码与失败原因一并保留。\n',encoding='utf-8',newline='\n')
files=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()]
(out/'manifest.json').write_text(json.dumps(dict(schema='vsl.phase-clock-freeze/1',source_commit=revision,
    combined_validation='not_passed',files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for p in files:assert sha(out/p['path'])==p['sha256']
print(json.dumps(dict(path=str(out),files=len(files),bytes=sum(p['bytes'] for p in files),commit=revision)))
