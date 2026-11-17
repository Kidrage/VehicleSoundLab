"""One-player dry review; keep the control fix separate from the timing hypothesis."""
import json
from pathlib import Path
import shutil

import soundfile as sf

from event_authoring.audio import sha
from event_designer.package import write_json


def build(root, output):
    output.mkdir(parents=True, exist_ok=False)
    tracks=[]
    for key,title,source,cue,note in (
        ('reference','A 原录音',root/'observation1/A35-40.5-monitor.wav',1.65,'原35–40.5秒，固定0.25倍；启动混合车内观察。'),
        ('original','V9 原衔接',root/'original1/mix.wav',.358,'保留原问题：接火后多出一次1→空挡切换。'),
        ('fixed','V10 仅修衔接',root/'fixed1/mix.wav',.358,'相同音色、事件和0.28秒工程拖转；取消启动后的虚假换挡。'),
        ('timing','V10 素材时序候选',root/'timing1/mix.wav',.358,'仅将工程拖转设为0.58秒；早期纹理→接火间隔0.572秒。'),
        ('continuous','V10 持续层独奏',root/'observation1/fixed1-continuous.wav',.358,'DNA、低频、细节与怠速交接；不含独立启动事件。'),
        ('events','V10 启动事件独奏',root/'observation1/fixed1-events.wav',.358,'只听早期持续纹理与接火补充；参数和V9相同。'),
    ):
        target=output/(key+'.wav');shutil.copy2(source,target)
        info=sf.info(target)
        tracks.append(dict(id=key,title=title,file=target.name,cue=cue,note=note,
                           frames=info.frames,duration=info.duration,channels=info.channels))
    for name,source in (
        ('fixed.recipe.json',root/'fixed1/startup.recipe.json'),
        ('timing.recipe.json',root/'timing1/startup.recipe.json'),
        ('observation.json',root/'observation1/report.json'),
        ('handoff.png',root/'observation1/handoff.png'),
    ):shutil.copy2(source,output/name)
    script='''const tracks=TRACKS;
const audio=document.querySelector('audio'),caption=document.querySelector('#caption');let selected=tracks[0],loaded=tracks[0],serial=0,objectUrl=null,request=null;
document.querySelector('#tracks').innerHTML=tracks.map(t=>`<button data-id="${t.id}" aria-pressed="${t.id===selected.id}">${t.title}</button>`).join('');
async function choose(t,initial=false){const rel=initial?-t.cue:audio.currentTime-loaded.cue,playing=!audio.paused;audio.pause();selected=t;const mine=++serial;if(request)request.abort();request=new AbortController();
 document.querySelectorAll('[data-id]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.id===t.id)));
 caption.textContent=t.note;
 try{const response=await fetch(t.file,{signal:request.signal});if(!response.ok)throw Error(response.status);const blob=await response.blob();if(mine!==serial)return;
 const next=URL.createObjectURL(blob),previous=objectUrl;objectUrl=next;audio.dataset.source=t.id;
 audio.addEventListener('loadedmetadata',()=>{if(mine!==serial)return;loaded=t;audio.currentTime=Math.max(0,Math.min(audio.duration-.01,rel+t.cue));if(playing)audio.play().catch(()=>{});},{once:true});
 audio.src=next;audio.load();if(previous)URL.revokeObjectURL(previous);
 }catch(e){if(e.name!=='AbortError')caption.textContent='音频载入失败，请刷新后重试。';}}
window.addEventListener('pagehide',()=>{if(request)request.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);});
document.querySelector('#tracks').addEventListener('click',e=>{const b=e.target.closest('[data-id]');if(b)choose(tracks.find(t=>t.id===b.dataset.id));});
document.querySelector('#cue').addEventListener('click',()=>{audio.currentTime=selected.cue;});choose(selected,true);'''.replace('TRACKS',json.dumps(tracks,ensure_ascii=False))
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>启动到怠速 · 衔接核查</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f9;color:#1b2940;font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1000px;margin:auto;padding:42px 24px 60px}small{color:#64718a;letter-spacing:.12em}h1{font-size:30px;line-height:1.3;margin:8px 0 18px}h2{font-size:20px;margin:0 0 12px}.card{background:white;border:1px solid #dde3ed;border-radius:14px;padding:24px;margin:20px 0}#tracks{display:flex;gap:10px;flex-wrap:wrap}button{font:inherit;cursor:pointer;border:1px solid #cbd5e4;border-radius:8px;background:#fff;color:inherit;padding:10px 15px}button[aria-pressed=true]{background:#245dcc;color:#fff;border-color:#245dcc}audio{width:100%;display:block;margin-top:20px}#caption{min-height:3.4em;color:#53627c}#cue{font-size:14px;padding:6px 12px}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:10px 6px;text-align:left;border-bottom:1px solid #e7ebf2}a{color:#245dcc}img{max-width:100%;height:auto}.links{display:flex;gap:18px;flex-wrap:wrap}p{margin:10px 0}@media(max-width:560px){main{padding:24px 14px}.card{padding:16px}h1{font-size:25px}button{font-size:14px;padding:9px 11px}th,td{font-size:12px;padding:8px 3px}}
</style><main><small>VEHICLE SOUND LAB · STARTUP → IDLE</small><h1>启动到怠速 · 衔接核查</h1>
<p>这轮先修正启动控制中断，再把素材时序作为独立候选。先比较“V9 原衔接／V10 仅修衔接”，重点听接火结束到怠速进入；再比较时序候选。</p>
<section class="card"><div id="tracks"></div><audio controls preload="metadata"></audio><p id="caption"></p><button id="cue">定位早期纹理起点</button><p>只有一个播放器。切换尽量保留相对早期标记的位置、音量和播放状态；三版C混音用同一输出增益，没有逐条归一化或房间处理。</p></section>
<section class="card"><h2>本轮具体改变</h2><table><tr><th>项目</th><th>V9 原版</th><th>V10 修正</th><th>时序候选</th></tr><tr><td>启动后额外换挡</td><td>1次</td><td>0次</td><td>0次</td></tr><tr><td>换挡阻挡怠速</td><td>225 ms</td><td>0 ms</td><td>0 ms</td></tr><tr><td>早期→接火</td><td>272 ms</td><td>272 ms</td><td>572 ms</td></tr><tr><td>工程峰值→怠速</td><td>1150→850 RPM</td><td>相同</td><td>相同</td></tr></table>
<p>素材的两个既定声学标记相隔570 ms，不能据此认定真实拖转时长、燃烧时刻或RPM。时序候选没有提高转速峰值，也没有新音色获批。</p></section>
<section class="card"><h2>分层与使用边界</h2><p>C演示组合了A车外行驶DNA、F2怠速和A启动车内观察事件，用于检验衔接；它不是同一录音视角的整段还原。启动事件保留最多12正弦模态与4程序噪声共振，持续DNA仍由原系统生成，不播放素材。</p><p>V10只修正静止、手动挡、启动前的挡位采用；自动策略、固定转速台架和运行中的真实换挡保留原路径。配方绑定新V10二进制，旧行程使用原冻结引擎。常驻窗口本轮未重启。</p><div class="links"><a download href="fixed.recipe.json">下载 V10 衔接配方</a><a download href="timing.recipe.json">下载时序候选</a><a href="observation.json">测量记录</a></div></section>
<details class="card"><summary>查看包络与分轨观察图</summary><img src="handoff.png" alt="原声与C输出的短时能量、持续层与事件、怠速权重"></details>
<script>SCRIPT</script></main></html>'''.replace('SCRIPT',script)
    (output/'index.html').write_text(html,encoding='utf-8')
    write_json(output/'report.json',dict(schema='vsl.startup-handoff-review/1',tracks=tracks,
        files={p.name:sha(p) for p in output.iterdir() if p.is_file()},
        single_player=True,spatial_processing=False,normalization=False,timbre_accepted=False))
