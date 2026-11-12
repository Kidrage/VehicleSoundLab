"""One-player dry band/whole audition for the fixed-budget source replacement."""
import argparse,html,json,shutil,subprocess,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--render',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',clips=[],source_sha256=sha(Path(__file__)),manual_browser_interaction=False)
try:
    verified=json.loads((a.render/'report.json').read_text(encoding='utf-8'))
    assert verified['result']=='render_technical_pass'
    r['render_report_sha256']=sha(a.render/'report.json')
    raw=a.render/'raw';signals={};manifest={}
    for name,file in [('reference','reference.wav'),('original','original.wav'),
                      ('replace35','replace_35_8121907_mix.wav'),('replace70','replace_70_8121907_mix.wav')]:
        x,rate=sf.read(raw/file,always_2d=True);assert rate==48000 and np.isfinite(x).all()
        signals[name]=x;manifest[name]={}
    bands={'whole':None,'low_high':[1200,1900],'presence':[1900,3000],'edge':[3000,6000],'fine':[6000,8000]}
    for name,x in signals.items():
        for band,limits in bands.items():
            y=x
            if limits:
                taps=signal.firwin(1025,limits,pass_zero=False,fs=48000)
                y=signal.fftconvolve(x,taps[:,None],mode='same',axes=0)
            for duration in ('short','long'):
                if duration=='long' and name=='reference':continue
                count=len(signals['reference']) if duration=='short' else 360000
                offset=0 if name=='reference' else 24000
                clip=y[offset:offset+count].copy()*.5;assert len(clip)==count
                # Short band references need common edge support for the FIR.
                n=1024 if duration=='short' else 240
                fade=np.sin(np.linspace(0,np.pi/2,n))**2
                clip[:n]*=fade[:,None];clip[-n:]*=fade[::-1,None]
                file=a.out/f'{name}_{band}_{duration}.wav';sf.write(file,clip,48000,subtype='PCM_24')
                assert abs(clip).max()<.95
                url='http://127.0.0.1:8789/'+file.relative_to(a.workspace).as_posix()
                with urllib.request.urlopen(url,timeout=10) as response:assert response.read()==file.read_bytes()
                done=subprocess.run(['ffmpeg','-v','error','-i',str(file),'-f','null','-'],capture_output=True,timeout=30)
                assert done.returncode==0
                manifest[name][band+'_'+duration]=file.name
                r['clips'].append(dict(file=file.name,frames=count,sha256=sha(file),HTTP_decode_pass=True))
    page='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>DNA 高频质感 · 共振细节替换</title><style>
*{box-sizing:border-box}body{font:16px system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;background:#f3f5f6;color:#18232b}main{background:white;border-radius:14px;padding:28px}h1{font-size:25px;margin:0 0 14px}p{line-height:1.7;color:#46545d}label{display:block;margin:20px 0 7px}select{font:inherit;width:100%;padding:10px;border:1px solid #b9c4ca;border-radius:7px;background:white}audio{width:100%;margin:24px 0 5px}.note{font-size:14px}#status{min-height:2em}
</style><main><h1>DNA 高频质感</h1><p>先听完整干声，切换原版／替换35%／70%。再选频段，检查锯齿般质感是否减少，以及有没有变成风声、砂噪或口哨声。</p>
<label for="version">声音</label><select id="version"><option value="original">原版 DNA＋相干低频</option><option value="replace35">候选 · 替换35%</option><option value="replace70">候选 · 替换70%</option><option value="reference">录音短参考</option></select>
<label for="band">频段</label><select id="band"><option value="whole">完整声音</option><option value="low_high">1.2–1.9 kHz</option><option value="presence">1.9–3 kHz</option><option value="edge">3–6 kHz</option><option value="fine">6–8 kHz</option></select>
<label for="duration">片段</label><select id="duration"><option value="long">持续生成片段 · 7.5秒</option><option value="short">短对照 · 约1.2秒（可选录音）</option></select>
<audio id="player" controls preload="metadata"></audio><p id="status" class="note"></p>
<p class="note">房间关闭 · 所有文件统一0.5源增益 · 分频未单独放大 · 无逐条响度补偿。切换后保留播放位置；只有一个播放器，不会叠播。</p>
<p class="note">候选持续生成新的激励，经过录音拟合的共振滤波与弱能量起伏，替换部分规整高频。低频分轨保持。录音参考来自同一归一化A车外情境，未循环；生成段不复制录音时间轨迹。本页是离线研究，音色尚未验收。</p></main>
<script>const files=__MANIFEST__;const version=document.getElementById('version'),band=document.getElementById('band'),duration=document.getElementById('duration'),player=document.getElementById('player'),status=document.getElementById('status');let revision=0;
function update(){const serial=++revision;const playing=!player.paused;const time=player.currentTime||0;player.pause();if(version.value==='reference')duration.value='short';player.src=files[version.value][band.value+'_'+duration.value];player.load();status.textContent=version.options[version.selectedIndex].text+' · '+band.options[band.selectedIndex].text;player.onloadedmetadata=()=>{if(serial!==revision)return;player.currentTime=Math.min(time,Math.max(0,player.duration-.02));if(playing)player.play().catch(()=>{});};}
version.addEventListener('change',update);band.addEventListener('change',update);duration.addEventListener('change',()=>{if(duration.value==='long'&&version.value==='reference')version.value='original';update();});update();</script></html>'''
    page=page.replace('__MANIFEST__',json.dumps(manifest,separators=(',',':')))
    (a.out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    r.update(result='35_clips_HTTP_decode_pass',page_sha256=sha(a.out/'index.html'),file_map=manifest,
             url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix(),
             common_gain=.5,short_fade_frames=1024,long_fade_frames=240,per_clip_gain=False)
    shutil.copy2(__file__,a.out/'executed_review.py')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],clips=len(r['clips']),url=r.get('url'))))
