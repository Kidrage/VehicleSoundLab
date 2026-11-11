"""Freeze offline state-colour and analysis-energy evidence without replacing runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import unquote
import zipfile
from html.parser import HTMLParser

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip(),'Commit final sources first'
summary=repo/'research/state_dna_v1_summary.json'
r=json.loads(summary.read_text(encoding='utf-8'))
assert r['result']=='pass' and not r['human_accepted'] and not r['runtime_changed']
assert not r['production_state_atlas_ready']
evidence=args.workspace/'references/analysis/state_dna_v1'
assert str(evidence)==r['evidence_root']
for field in ('source_sha256','runtime_sha256'):
    for name,expected in r[field].items():assert sha(repo/name)==expected,name
for name,expected in r['evidence_sha256'].items():assert sha(evidence/name)==expected,name
for record in r['review']['records']:assert sha(args.workspace/record['file'])==record['sha256']
assert sha(r['review']['page'])==r['review']['page_sha256']
qa=json.loads((evidence/'review/browser_qa.json').read_text(encoding='utf-8'))
assert qa['result']=='pass' and qa['muted'] and qa['page_sha256']==r['review']['page_sha256']
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
destination=args.workspace/'baselines/state_dna_v1'
destination.mkdir(exist_ok=False)
shutil.copytree(evidence,destination/'evidence')
(destination/'docs').mkdir()
for p in (summary,repo/'research/工况声纹分离V1.md'):
    shutil.copy2(p,destination/'docs'/p.name)
shutil.copy2(r['review']['page'],destination/'docs')
page=destination/'docs'/Path(r['review']['page']).name
portable=page.read_text(encoding='utf-8').replace('../references/analysis/state_dna_v1/','../evidence/')
page.write_text(portable,encoding='utf-8')
class Assets(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key=='src':assert (page.parent/unquote(value)).is_file(),value
Assets().feed(portable)
upstream=args.workspace/'references/analysis/coherent_low_v1/upstream'
for name,expected in r['upstream']['files'].items():assert sha(upstream/name)==expected
shutil.copytree(upstream,destination/'upstream')
(destination/'bin').mkdir()
probe=repo/'handoff-build/bin/Release/VslSoundDna_probe.exe'
assert sha(probe)==json.loads((evidence/'observed_v2/report.json').read_text(encoding='utf-8'))['probe_sha256']
shutil.copy2(probe,destination/'bin')
subprocess.run(['git','archive','--format=zip','--output='+str(destination/'source.zip'),revision],cwd=repo,check=True)
with zipfile.ZipFile(destination/'source.zip') as archive:assert archive.testzip() is None
(destination/'README.txt').write_text('工况声纹分离与分析窗能量预算V1\n提交：'+revision+'\n'
    '本包是离线研究证据，不替换驾驶程序或已认可音色。\n'
    '最终依据：evidence/observed_v2、controls_v2、energy_budget、review/browser_qa.json。\n'
    '早期路径未连通和修订输出保留在其他目录，不当作最终结果。\n'
    '三组voice.model为同一C核心的短片段诊断，上升段只有约7周期。\n'
    '原始float生成峰值可超过1；试听副本采用统一0.25增益，没有逐条归一化。\n'
    '原始录音与完整旧工具沿用既有交接包；docs中的HTML可独立打开本包音频与图片。\n'
    '高频预算结论：中心谐波读取对OSC功率正确，对理想宽带噪声仅保留3/8；不能整体增益补偿DNA。\n'
    '驾驶工况谱形、谐波间残差层与主观听评仍需继续。\n',encoding='utf-8')
files=[dict(path=p.relative_to(destination).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
    for p in sorted(destination.rglob('*')) if p.is_file()]
manifest=dict(schema='vsl.state-dna-freeze/1',source_commit=revision,human_accepted=False,files=files)
(destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
for row in files:assert sha(destination/row['path'])==row['sha256']
print(json.dumps(dict(path=str(destination),commit=revision,files=len(files),bytes=sum(v['bytes'] for v in files)),ensure_ascii=False))
