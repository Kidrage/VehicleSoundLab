"""One-player same-gain idle comparison; no room or PCM source looping."""
import argparse,json,shutil,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',clips=[])
try:
    shutil.copy2(__file__,a.out/'executed_review.py')
    parent=a.workspace/'references/analysis/idle_modal_v1/trial4'
    signals={};seeds=[149921,277139,381611]
    signals['reference'],_=sf.read(parent/'F2_holdout.wav',always_2d=True)
    for seed in seeds:
        signals[f'original_{seed}'],_=sf.read(parent/f'mix_{seed}.wav',always_2d=True)
        for method in ['fine','dynamic']:
            signals[f'{method}_{seed}'],_=sf.read(a.input/f'{method}_{seed}.wav',always_2d=True)
    gain=min(1.,.85/max(abs(x).max() for x in signals.values()))
    files={}
    for key,x in signals.items():
        files[key]={}
        for band,limits in [('whole',None),('mid',[400,2200]),('high',[2200,14000])]:
            y=x if limits is None else signal.fftconvolve(x,signal.firwin(2049,limits,fs=48000,pass_zero=False)[:,None],mode='same',axes=0)
            y=y*gain;fade=np.sin(np.linspace(0,np.pi/2,1024))**2
            y[:1024]*=fade[:,None];y[-1024:]*=fade[::-1,None]
            path=a.out/f'{key}_{band}.wav';sf.write(path,y,48000,subtype='PCM_24')
            decoded,rate=sf.read(path,always_2d=True);assert rate==48000 and abs(decoded-y).max()<=2**-23
            with urllib.request.urlopen('http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix(),timeout=10) as response:
                assert response.read()==path.read_bytes()
            files[key][band]=path.name;r['clips'].append(dict(file=path.name,frames=len(y),sha256=sha(path)))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>怠速细节 · V2</title><style>*{box-sizing:border-box}body{font:16px/1.65 system-ui,sans-serif;background:#f3f5f6;color:#1d2933;margin:0;padding:32px 18px}main{max-width:720px;margin:auto;padding:26px;background:white;border-radius:14px}h1{font-size:24px;margin:0 0 12px}p{color:#52606c;font-size:14px}label{display:block;margin:18px 0 5px}select,audio{width:100%;font:inherit}select{padding:10px;border:1px solid #c6ced6;border-radius:7px;background:white}audio{margin-top:24px}#status{min-height:1.7em}</style>
<main><h1>怠速细节 · V2</h1><p>先听原录音，再比较上一版与两条新候选。重点听机械颗粒、平直嗡鸣、沙噪和不自然的起伏。</p>
<label for="mode">声音</label><select id="mode"><option value="reference">原录音 · F2 尾排（3秒）</option><option value="original" selected>上一版怠速（12秒）</option><option value="fine">新候选 · 细化共振（12秒）</option><option value="dynamic">新候选 · 共振＋幅度起伏（12秒）</option></select>
<label for="band">频段</label><select id="band"><option value="whole">完整声音</option><option value="mid">400–2200 Hz</option><option value="high">2.2–14 kHz</option></select>
<label for="seed">生成组</label><select id="seed"><option>149921</option><option>277139</option><option>381611</option></select>
<audio id="player" controls preload="metadata"></audio><p id="status" role="status">准备中…</p>
<p>原录音取 F2 的9–12秒，候选仅用6–9秒提取参数。所有版本使用同一增益 __GAIN__，没有逐条响度补偿或房间处理。请暂停其他发声窗口。</p>
<p>新候选保留上一版13条主声线，细化其余频谱；第二条另加入新生成的缓慢幅度起伏。没有原片循环或频率抖动。三组随机序列全部保留。</p>
<p>F2 有效车声近单声道；本轮保持素材声道关系。此页是固定怠速的离线候选，尚未替换驾驶 Demo。</p></main>
<script>const files=__FILES__;const player=document.querySelector('#player'),mode=document.querySelector('#mode'),band=document.querySelector('#band'),seed=document.querySelector('#seed'),status=document.querySelector('#status');const cache=new Map();let revision=0;
function key(){return mode.value==='reference'?'reference':mode.value+'_'+seed.value;}
async function update(){const serial=++revision,at=player.currentTime||0,playing=!player.paused;player.pause();seed.disabled=mode.value==='reference';status.textContent='准备中…';try{const name=files[key()][band.value];if(!cache.has(name))cache.set(name,fetch(name).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.blob();}).then(blob=>URL.createObjectURL(blob)));const url=await cache.get(name);if(serial!==revision)return;player.addEventListener('loadedmetadata',()=>{if(serial!==revision)return;player.currentTime=Math.min(at,Math.max(0,player.duration-.02));status.textContent=mode.options[mode.selectedIndex].text+' · '+band.options[band.selectedIndex].text;if(playing)player.play().catch(()=>{});},{once:true});player.src=url;player.load();}catch(e){if(serial===revision)status.textContent='音频读取失败，请刷新。';}}
for(const e of [mode,band,seed])e.addEventListener('change',update);window.addEventListener('pagehide',()=>{for(const p of cache.values())p.then(url=>URL.revokeObjectURL(url)).catch(()=>{});});update();</script></html>'''
    page=page.replace('__FILES__',json.dumps(files,separators=(',',':'))).replace('__GAIN__',format(gain,'.6g'))
    (a.out/'index.html').write_text(page,encoding='utf-8')
    assert page.count('<audio ')==1
    r.update(result='single_player_shared_gain_comparison_prepared',common_gain=gain,files=files,
        url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix(),listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=r['result'],url=r.get('url')),ensure_ascii=False))
