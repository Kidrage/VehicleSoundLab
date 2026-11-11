"""Create a shared-gain comparison of LF envelope partitioning, with solo bus."""
import argparse
import csv
import html
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import soundfile as sf
from drive_evidence_v1.sources import sha

root=args.workspace/'references/analysis/harmonic_body_v1'
controls=root/'controls'
assert json.loads((controls/'verification.json').read_text(encoding='utf-8'))['result']=='pass'
out=root/'review';out.mkdir(exist_ok=False)
assets=out/'assets';assets.mkdir()
tracks=[('zero','原混音 · 低频分层0%','原始DNA使用原来的工况包络。'),
    ('layered','低频分层100%','同一组谐波的低频改用独立机体包络，重点听换挡和松油。'),
    ('solo','只听分出的低频层','与完整混音使用相同主音量，单听可能较轻。')]
for name in ('zero','layered'):
    shutil.copy2(controls/(name+'_render.wav'),assets/(name+'.wav'))
body,rate=sf.read(controls/'layered_harmonic_body.wav',always_2d=True)
sf.write(assets/'solo.wav',body*.2,rate,subtype='FLOAT')
with (controls/'layered_trace.csv').open(encoding='utf-8',newline='') as stream:
    rows=list(csv.DictReader(stream))
first_shift=next(float(r['seconds']) for r in rows if int(r['shifts'])>0)
def page(prefix):
    cards=''.join(f'<article><h2>{html.escape(title)}</h2><p>{html.escape(note)}</p>'
        f'<audio id="{name}" controls preload="metadata" src="{prefix}{name}.wav"></audio></article>'
        for name,title,note in tracks)
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+'''
<title>驾驶低频分层 V1</title><style>
body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;background:#f3f5f7;color:#15212b;margin:0}
main{max-width:840px;margin:32px auto;padding:0 20px}h1{font-size:28px}h2{font-size:19px;margin:0}
article{background:white;border:1px solid #d9e0e6;border-radius:10px;padding:20px;margin:16px 0}
p{margin:10px 0;color:#465562}audio{width:100%;margin-top:8px}button{padding:9px 14px;font:inherit;cursor:pointer}
small{display:block;color:#53616d}a{color:#145c91}</style><main><h1>驾驶低频分层 V1</h1>
<p>先暂停其他发声窗口。比较换挡、松油后低频能否自然延续，是否出现嗡鸣或颤动。</p>
<p>两版使用同一驾驶轨迹、DNA和高频细节；主音量相同，没有逐版响度补偿。当前是驻车车外锚点的模拟驾驶，音色仍待听评。</p>
<button id="seek">定位第一次模拟换挡前</button>'''+cards+f'''
<small>这里分出的是已有OSC中的相干低频；没有增加录音循环或新提取的物理声源。低频分层0%保留旧输出。</small>
<script>const players=[...document.querySelectorAll('audio')];
players.forEach(a=>a.addEventListener('play',()=>players.forEach(b=>{{if(b!==a)b.pause()}})));
document.querySelector('#seek').onclick=()=>players.forEach(a=>a.currentTime={max(0,first_shift-.5):.3f});</script></main></html>'''
(out/'index.html').write_text(page('assets/'),encoding='utf-8')
published=args.workspace/'research/驾驶低频分层V1.html'
assert not published.exists()
published.write_text(page('../references/analysis/harmonic_body_v1/review/assets/'),encoding='utf-8')
report=dict(schema='vsl.harmonic-body-review/1',human_accepted=False,master_gain=.2,
    first_simulated_shift_seconds=first_shift,tracks=[dict(name=n,file=n+'.wav',sha256=sha(assets/(n+'.wav'))) for n,_,_ in tracks],
    source_sha256={Path(__file__).relative_to(repo).as_posix():sha(Path(__file__))})
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(str(published))
