"""Make a concise listening page and driving-coverage figure from verified C audio."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import sys
from urllib.parse import quote

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--verified',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

verification=json.loads((args.verified/'verification.json').read_text(encoding='utf-8'))
assert verification['result']=='pass' and verification['accepted'] is False
directory=args.verified/'audition'
page=args.workspace/'research/多锚点驾驶V1.html'
assert not page.exists()
directory.mkdir(exist_ok=False)
cases=[('lower',2,'约7276 RPM · 较低锚点'),('mid',2,'约7529 RPM · 两锚点之间'),
    ('upper',2,'约7782 RPM · 较高锚点'),('auto',0,'自动驾驶 · DNA'),
    ('neutral',0,'空挡补油 · DNA'),('downshift',0,'升降挡与制动 · DNA'),
    ('shifts_events',0,'换挡／收油 · 加旧程序事件对照')]
records=[];cards=[]
for name,start,label in cases:
    source=args.verified/(name+'_render.wav')
    row=next(r for r in verification['runs'] if r['name']==name)
    assert sha(source)==row['files_sha256'][source.name]
    audio,rate=sf.read(source,always_2d=True)
    assert rate==48000 and audio.shape[1]==2
    audio=audio[int(start*48000):].copy()
    envelope=np.ones(len(audio));envelope[:240]=np.linspace(0,1,240);envelope[-240:]=np.linspace(1,0,240)
    target=directory/(name+'.wav')
    sf.write(target,audio*envelope[:,None],48000,subtype='PCM_24')
    records.append(dict(name=name,source_sha256=sha(source),source_start_seconds=start,
        sha256=sha(target),frames=len(audio),processing='5ms endpoint fades, PCM24; common C gain0.5; no per-clip normalization'))
    url='../'+target.relative_to(args.workspace).as_posix()
    cards.append(f'<div class="card"><label>{html.escape(label)}</label><audio controls preload="metadata" src="{quote(url,safe="/.")}"></audio></div>')

trace=np.genfromtxt(args.verified/'auto_trace.csv',delimiter=',',names=True)
fig,axes=plt.subplots(3,1,figsize=(10,6.6),sharex=True,layout='constrained')
t=trace['seconds'];lo,hi=np.array([60.634271286273396,64.84675603879224])*120
axes[0].axhspan(lo,hi,color='#37a677',alpha=.18,label='Recorded anchor interval')
axes[0].plot(t,trace['rpm'],label='Driving controller RPM',color='#273e62',lw=1)
axes[0].plot(t,trace['root_hz']*120,label='Smoothed OSC clock x120',color='#be6f16',lw=.9,alpha=.85)
axes[0].set_ylabel('RPM');axes[0].legend(loc='lower right',fontsize=8)
axes[0].set_title('E cabin atlas: two high-RPM anchors; boundary timbre outside the band')
axes[1].plot(t,trace['envelope'],color='#733f85',lw=1,label='DNA state envelope')
axes[1].fill_between(t,0,1,where=trace['operating']==5,step='post',color='#d4824e',alpha=.25,label='Shift cut state')
axes[1].set_ylabel('Gain');axes[1].legend(loc='upper right',fontsize=8)
axes[2].step(t,trace['gear'],where='post',label='Gear',color='#273e62',lw=1)
axes[2].set_ylabel('Gear');axes[2].set_xlabel('Time (s)');axes[2].set_yticks(range(8))
for ax in axes:ax.grid(alpha=.15);ax.set_xlim(0,30)
figure=args.verified/'drive_trace.png';fig.savefig(figure,dpi=160);plt.close(fig)

page.write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>多锚点 DNA · 驾驶接入 V1</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:800px;margin:30px auto;padding:0 20px;background:#f4f5f5;color:#20272b}h1{font-size:25px}h2{font-size:19px}.card{padding:12px 16px;margin:12px 0;background:white;border:1px solid #dce1e3;border-radius:8px}label{display:block;margin-bottom:8px}audio{width:100%;height:42px}img{width:100%}details{margin:24px 0}</style>
<h1>多锚点 DNA · 驾驶接入 V1</h1><p>先听三个稳定音高，再听空挡补油与自动驾驶经过高转区的变化，关注是否有拍频、空洞或突然变声。</p>
<p>本轮使用 E 的两个高转车内片段。约7276–7782 RPM有锚点依据；低转和更高转沿用边界声纹，仍待补充素材。当前是DNA单层驾驶验证，尚未加入独立车内低频、进气或噪音层。A车外认可版本保持独立。</p>
<h2>稳定音高</h2>'''+''.join(cards[:3])+'''<h2>驾驶过程</h2><p>前面三条驾驶声只有DNA；最后一条加入原有程序事件，供检查触发。全部使用同一输出增益，仅做5ms端点淡化，没有逐条响度补偿。</p>'''+''.join(cards[3:])+f'''
<details><summary>转速覆盖与状态记录</summary><img alt="驾驶转速、DNA包络与挡位" src="../{figure.relative_to(args.workspace).as_posix()}"><p>图中绿色仅表示两个录音锚点之间的转速范围，不代表全部负载和工况均有对应实录。新原生驾驶UI、设备稳定性与本轮听感仍待验证；12通道文件另存，不在网页折叠播放。</p></details>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{{if(b!==a)b.pause()}})))</script></html>''',encoding='utf-8')
(directory/'review.json').write_text(json.dumps(dict(schema='vsl.atlas-drive-review/1',
    verification_sha256=sha(args.verified/'verification.json'),records=records,
    page=str(page),page_sha256=sha(page),figure_sha256=sha(figure),builder_sha256=sha(__file__)),
    ensure_ascii=False,indent=2),encoding='utf-8')
print(page)
