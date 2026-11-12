"""Publish isolated startup texture listening without changing the deployed renderer."""
import argparse
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import quote,urljoin
from urllib.request import urlopen

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--verified',type=Path,required=True);p.add_argument('--ffmpeg',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read,sha

a.out.mkdir(parents=True,exist_ok=False);(a.out/'audio').mkdir()
shutil.copy2(__file__,a.out/'executed_review.py')
r=dict(schema='vsl.startup-texture-review/1',result='running',clips=[],
       source_sha256=sha(__file__),verification_report_sha256=sha(a.verified/'report.json'),
       human_accepted=False,browser_interaction_checked=False)
try:
    proof=json.loads((a.verified/'report.json').read_text(encoding='utf-8'))
    assert proof['result']=='isolated_candidate_verified'
    for row in proof['renders']:
        assert sha(a.verified/'renders'/f'{row["mode"]}_{row["seed"]}.wav')==row['sha256']
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    short=x[round((36.65-33)*48000):round((37.12-33)*48000)]
    held,rate=sf.read(a.verified/'renders/held_48271.wav',always_2d=True);assert rate==48000
    old,_=sf.read(a.verified/'renders/old_48271.wav',always_2d=True)
    new,_=sf.read(a.verified/'renders/new_48271.wav',always_2d=True)
    cases=[('context','A 原始启动语境 · 33–40s',x,1.,'实录，车内混合声。'),
           ('reference','A 启动前段实录 · 36.65–37.12s',short,1.,'这是整体录音，尚未分离纯起动机。'),
           ('texture','新 OSC 纹理 · 等时短段',held[19200:19200+len(short)],1.,'合成300–8000Hz的平均谱形与左右相关；没有复制原录音包络。'),
           ('held','新 OSC 纹理 · 连续保持',held,1.,'人为保持开关3.25秒，检查持续性；不是这台车的实际拖转时长。')]
    # One explicit comparison-only RMS target for both driver-gated event solos.
    # This compensates the legacy event's much lower level without changing model data.
    target=.04
    for key,title,y in [('old','旧启动附加声 · 两次驾驶器触发',old),('new','新启动纹理 · 两次驾驶器触发',new)]:
        gain=target/float(np.sqrt(np.mean(y*y)))
        cases.append((key,title,y,gain,'只听附加层，没有DNA或接火轰鸣。两次触发沿用同一驾驶器；这两条先匹配整段RMS。'))
    for key,title,y,gain,note in cases:
        y=y.copy()*gain*.5
        fade=min(240,len(y)//2);y[:fade]*=np.linspace(0,1,fade)[:,None];y[-fade:]*=np.linspace(1,0,fade)[:,None]
        assert np.isfinite(y).all() and np.max(abs(y))<.9
        path=a.out/'audio'/f'{key}.wav';sf.write(path,y,48000,subtype='PCM_24')
        done=subprocess.run([str(a.ffmpeg),'-v','error','-i',str(path),'-f','null','-'],capture_output=True,timeout=30)
        assert done.returncode==0,done.stderr
        r['clips'].append(dict(key=key,title=title,note=note,frames=len(y),comparison_RMS_gain=gain,
            common_gain=.5,fade_samples=fade,peak=float(np.max(abs(y))),sha256=sha(path),FFmpeg_decodes=True))
    prefix='../references/analysis/startup_texture_v1/'+a.out.name+'/audio/'
    body='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>启动机械纹理 V1</title>'
    body+='<style>body{font:16px/1.65 system-ui;max-width:850px;margin:30px auto;padding:0 18px;background:#f5f6f6;color:#20282b}h1{font-size:25px}h2{font-size:19px}article{background:white;border:1px solid #dce1e3;border-radius:8px;padding:14px 16px;margin:12px 0}audio{width:100%;height:42px}.note{color:#566269;font-size:14px}</style>'
    body+='<h1>启动机械纹理 V1</h1><p>先暂停其他发声窗口。先听原始语境，再比较短段实录与OSC纹理。</p><p><strong>这一轮只研究启动前段的机械纹理。</strong>接火、低频建立和稳定运行仍需单独完善；下面没有把新纹理冒充完整启动。</p>'
    for i,clip in enumerate(r['clips']):
        if i==0:body+='<h2>素材与持续生成</h2>'
        if i==4:body+='<h2>同一驾驶器的启动开关</h2><p class="note">0.15秒与2.50秒发出启动命令；拖转时长沿用现有工程配方0.28秒。这里不复刻视频的物理启动时序。</p>'
        body+='<article><strong>'+html.escape(clip['title'])+'</strong><p class="note">'+html.escape(clip['note'])+'</p><audio controls preload="metadata" src="'+prefix+clip['key']+'.wav"></audio></article>'
    body+='<p class="note">前四条只用共同0.5增益和5ms首尾淡化。最后两条先分别匹配整段RMS到0.04，再用共同0.5增益；补偿只用于试听，不进入模型或C代码。短实录与持续合成没有逐条响度补偿。合成使用16个频带的统计参数，不含PCM、录音循环或逐帧幅度轨迹。</p>'
    body+='<p class="note">单个平均谱形会丢失真实前段的频谱变化：训练片段前后半段某频带相差约5.83dB。候选尚未接入默认监听窗口，未通过自然度或完整启动听评。</p>'
    body+='<script>document.querySelectorAll("audio").forEach(a=>a.addEventListener("play",()=>document.querySelectorAll("audio").forEach(b=>{if(a!==b)b.pause()})))</script></html>'
    page=a.workspace/'research/启动机械纹理V1.html';assert not page.exists()
    page.write_text(body,encoding='utf-8',newline='\n');shutil.copy2(page,a.out/'page.html')
    url='http://127.0.0.1:8789/research/'+quote(page.name)
    with urlopen(url,timeout=15) as response:assert response.read()==page.read_bytes()
    for relative in re.findall(r'<audio[^>]*src="([^"]+)"',body):
        with urlopen(urljoin(url,relative),timeout=15) as response:
            assert response.read()==(a.out/'audio'/Path(relative).name).read_bytes()
    r.update(result='pass',page=url,page_sha256=sha(page),HTTP_bytes_verified=True,
        meaning='Partial early-startup layer candidate and real driver permission proof, not whole-state restoration')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],clips=len(r['clips']),page=r['page']),ensure_ascii=True))
