"""One-player dry idle comparison, preserving the prior fast-grain candidate."""
import argparse,json,sys,urllib.request,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_review.py')
r=dict(result='running',clips=[])
try:
    assert load(a.input/'report.json')['result']=='conditioned_detail_candidates_pending_listening'
    signals={};inputs={}
    paths={'reference_mix':a.workspace/'baselines/idle_texture_v2/inputs/F2_holdout.wav'}
    for seed in [149921,277139,381611]:
        for mode in ['000','050','100','fast']:
            for bus in ['mix','detail']:
                paths[f'{mode}_{seed}_{bus}']=(a.workspace/f'baselines/idle_microtexture_v1/evidence/trial1/{bus}_050_{seed}.wav'
                    if mode=='fast' else a.input/f'{bus}_{mode}_{seed}.wav')
    for key,path in paths.items():
        signals[key],rate=sf.read(path,always_2d=True);assert rate==48000;inputs[key]=dict(path=str(path),sha256=sha(path))
    gain=min(1.,.85/max(abs(x).max() for x in signals.values()));files={}
    for key,x in signals.items():
        y=x.copy()*gain;fade=np.sin(np.linspace(0,np.pi/2,1024))**2;y[:1024]*=fade[:,None];y[-1024:]*=fade[::-1,None]
        path=a.out/(key+'.wav');sf.write(path,y,48000,subtype='PCM_24')
        decoded,rate=sf.read(path,always_2d=True);assert abs(decoded-y).max()<=2**-23
        with urllib.request.urlopen('http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix(),timeout=10) as response:
            assert response.read()==path.read_bytes()
        files[key]=path.name;r['clips'].append(dict(key=key,frames=len(y),sha256=sha(path)))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>怠速 · 主声线带动细节</title><style>*{box-sizing:border-box}body{margin:0;padding:28px 16px;background:#eef1f3;color:#182e39;font:16px/1.65 system-ui,sans-serif}main{max-width:660px;margin:auto;background:white;padding:26px;border-radius:14px}h1{font-size:24px;line-height:1.4;margin:0 0 12px}p{font-size:14px;color:#51636c}label{display:block;margin:15px 0 5px}select,audio{width:100%;font:inherit}select{padding:10px;border:1px solid #bccad0;border-radius:7px;background:white;color:inherit}audio{margin-top:22px}#status{min-height:1.7em}.note{font-size:13px}</style>
<main><h1>怠速 · 主声线带动细节</h1><p>先在“前轮随机颗粒”和“主声线带动 · 50%”之间切换，再听100%。比较发动机的颗粒与连贯感，也留意嗡鸣、沙声和颤动。</p>
<label for="mode">声音</label><select id="mode"><option value="fast" selected>前轮 · 随机颗粒50%</option><option value="000">基础 · 无颗粒调制</option><option value="050">主声线带动 · 50%</option><option value="100">主声线带动 · 100%</option><option value="reference">原录音 · F2尾排（3秒）</option></select>
<label for="bus">监听</label><select id="bus"><option value="mix">完整声音</option><option value="detail">只听细节</option></select>
<label for="seed">生成组</label><select id="seed"><option>149921</option><option>277139</option><option>381611</option></select>
<audio id="player" controls preload="metadata"></audio><p id="status" role="status">准备中…</p>
<p>新候选让高频细节的强弱跟随已有主声线，关系来自怠速素材。各版主声线与细节滤波器相同，没有额外增亮或房间处理。</p>
<p>全部使用同一增益 __GAIN__，未逐条补偿响度。生成声音持续12秒；原录音用于对照。请暂停其他发声窗口。</p>
<p class="note">这次只比较固定怠速音色，尚未替换驾驶Demo。新的强弱关系不等于完整恢复发动机机械结构。</p></main>
<script>const files=__FILES__,player=document.querySelector('#player'),mode=document.querySelector('#mode'),bus=document.querySelector('#bus'),seed=document.querySelector('#seed'),status=document.querySelector('#status'),cache=new Map();let revision=0;
async function update(){const serial=++revision,at=player.currentTime||0,playing=!player.paused;player.pause();const ref=mode.value==='reference';seed.disabled=ref;bus.disabled=ref;if(ref)bus.value='mix';status.textContent='准备中…';try{const key=ref?'reference_mix':mode.value+'_'+seed.value+'_'+bus.value,name=files[key];if(!cache.has(name))cache.set(name,fetch(name).then(r=>{if(!r.ok)throw Error(r.status);return r.blob();}).then(b=>URL.createObjectURL(b)));const url=await cache.get(name);if(serial!==revision)return;player.addEventListener('loadedmetadata',()=>{if(serial!==revision)return;player.currentTime=Math.min(at,Math.max(0,player.duration-.02));status.textContent=mode.selectedOptions[0].text+' · '+bus.selectedOptions[0].text;if(playing)player.play().catch(()=>{});},{once:true});player.src=url;player.load();}catch(e){if(serial===revision)status.textContent='读取失败，请刷新。'}}
for(const el of [mode,bus,seed])el.addEventListener('change',update);window.addEventListener('pagehide',()=>{for(const p of cache.values())p.then(u=>URL.revokeObjectURL(u)).catch(()=>{});});update();</script></html>'''
    page=page.replace('__GAIN__',format(gain,'.6g')).replace('__FILES__',json.dumps(files,separators=(',',':')))
    (a.out/'index.html').write_text(page,encoding='utf-8');assert page.count('<audio ')==1
    r.update(result='single_player_conditioned_detail_review',common_gain=float(gain),files=files,inputs=inputs,
        url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix(),listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r.get('url',r['result']))
