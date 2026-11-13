"""Simple one-player comparison of fixed-idle core amplitude motion."""
import argparse,json,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',clips=[])
try:
    (a.out/'executed_review.py').write_bytes(Path(__file__).read_bytes())
    report=load(a.input/'report.json');assert report['result']=='amplitude_only_fixed_idle_candidates_pending_listening'
    reference=a.workspace/'references/analysis/idle_modal_v1/trial4/F2_holdout.wav'
    assert sha(reference)==sha(a.workspace/'baselines/idle_texture_v2/inputs/F2_holdout.wav')
    signals={'reference_mix':sf.read(reference,always_2d=True)[0]}
    for seed in report['plan']['seeds']:
        for amount in report['plan']['amounts']:
            label=f'{round(amount*100):03d}'
            for bus in ['mix','core']:
                name=f'{label}_{seed}_{bus}';signals[name]=sf.read(a.input/f'{bus}_{label}_{seed}.wav',always_2d=True)[0]
    gain=min(1.,.85/max(float(abs(x).max()) for x in signals.values()));files={}
    for key,x in signals.items():
        output=x.copy()*gain;fade=np.sin(np.linspace(0,np.pi/2,1024))**2
        output[:1024]*=fade[:,None];output[-1024:]*=fade[::-1,None]
        path=a.out/f'{key}.wav';sf.write(path,output,48000,subtype='PCM_24')
        actual,rate=sf.read(path,always_2d=True);assert rate==48000 and abs(actual-output).max()<=2**-23
        with urllib.request.urlopen('http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix(),timeout=10) as response:
            assert response.read()==path.read_bytes()
        files[key]=path.name;r['clips'].append(dict(key=key,frames=len(output),sha256=sha(path)))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>怠速主声线 · 起伏对照</title><style>*{box-sizing:border-box}body{margin:0;padding:32px 18px;background:#f3f5f6;color:#172b36;font:16px/1.65 system-ui,sans-serif}main{max-width:690px;margin:auto;background:white;border-radius:14px;padding:28px}h1{font-size:24px;line-height:1.35;margin:0 0 14px}p{font-size:14px;color:#52616b}label{display:block;margin:17px 0 5px}select,audio{width:100%;font:inherit}select{padding:10px;border:1px solid #c6d0d5;border-radius:7px;background:white;color:inherit}audio{margin-top:24px}#status{min-height:1.7em}small{font-size:13px}</style>
<main><h1>怠速主声线 · 起伏对照</h1><p>先比较基准和50%，再切到“只听主声线”。重点听发动机是否更有活力，以及有没有多余的忽大忽小。</p>
<label for="mode">声音</label><select id="mode"><option value="000" selected>基准 · 前轮细化共振候选</option><option value="050">主声线起伏 · 50%</option><option value="100">主声线起伏 · 100%</option><option value="reference">原录音 · F2 尾排（3秒）</option></select>
<label for="bus">监听</label><select id="bus"><option value="mix">完整声音</option><option value="core">只听主声线</option></select>
<label for="seed">生成组</label><select id="seed"><option>149921</option><option>277139</option><option>381611</option></select>
<audio id="player" controls preload="metadata"></audio><p id="status" role="status">准备中…</p>
<p>三版音高、平均相位和共振细节相同，只改变主声线的缓慢音量起伏。候选持续12秒，使用新生成的变化；没有原片循环或房间处理。</p>
<p>所有音频使用同一增益 __GAIN__，未逐条补偿响度。原录音取9–12秒，参数只从6–9秒提取。请暂停其他发声窗口。</p>
<p><small>此页是固定怠速的离线候选，尚未替换驾驶Demo；基准也仍待听评。素材有效车声近单声道，本轮保持其声道关系。</small></p></main>
<script>const files=__FILES__;const player=document.querySelector('#player'),mode=document.querySelector('#mode'),bus=document.querySelector('#bus'),seed=document.querySelector('#seed'),status=document.querySelector('#status');const cache=new Map();let revision=0;
async function update(){const serial=++revision,at=player.currentTime||0,playing=!player.paused;player.pause();const reference=mode.value==='reference';seed.disabled=reference;bus.disabled=reference;if(reference)bus.value='mix';status.textContent='准备中…';try{const key=reference?'reference_mix':mode.value+'_'+seed.value+'_'+bus.value,name=files[key];if(!cache.has(name))cache.set(name,fetch(name).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.blob();}).then(blob=>URL.createObjectURL(blob)));const url=await cache.get(name);if(serial!==revision)return;player.addEventListener('loadedmetadata',()=>{if(serial!==revision)return;player.currentTime=Math.min(at,Math.max(0,player.duration-.02));status.textContent=mode.selectedOptions[0].text+' · '+bus.selectedOptions[0].text;if(playing)player.play().catch(()=>{});},{once:true});player.src=url;player.load();}catch(e){if(serial===revision)status.textContent='音频读取失败，请刷新。';}}
for(const control of [mode,bus,seed])control.addEventListener('change',update);window.addEventListener('pagehide',()=>{for(const promise of cache.values())promise.then(url=>URL.revokeObjectURL(url)).catch(()=>{});});update();</script></html>'''
    page=page.replace('__GAIN__',format(gain,'.6g')).replace('__FILES__',json.dumps(files,separators=(',',':')))
    (a.out/'index.html').write_text(page,encoding='utf-8');assert page.count('<audio ')==1
    r.update(result='single_player_core_amplitude_review_prepared',common_gain=gain,files=files,
        source_profile_sha256=sha(a.input/'profile.json'),reference_sha256=sha(reference),
        url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix(),listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],url=r.get('url')),ensure_ascii=False))
