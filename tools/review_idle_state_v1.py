"""A single-player preview of the existing controlled C source transition."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_review.py')
r=json.loads((a.input/'report.json').read_text(encoding='utf-8'))
assert r['result']=='continuous_idle_state_and_all84_legacy_WAVs_verified' and r['level_gain']>0
for label,folder in [('original','disabled'),('candidate','enabled')]:
    shutil.copy2(a.input/folder/'C_mix.wav',a.out/(label+'.wav'))
added,rate=sf.read(a.input/'enabled/C_idle_added.wav',always_2d=True)
sf.write(a.out/'idle_solo.wav',added*.25,rate,subtype='FLOAT')
trace=np.fromfile(a.input/'enabled/C_trace.f64',dtype='<f8').reshape((-1,6))
data=[[float(row[0]),int(row[1]),int(row[2]),float(row[4])] for row in trace[::240]]
(a.out/'state.json').write_text(json.dumps(data,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>怠速状态衔接 · C 技术预览</title>
<style>body{font:16px/1.6 system-ui,sans-serif;background:#f3f4f6;color:#242831;margin:0;padding:32px 18px}main{max-width:740px;margin:auto;background:white;border-radius:16px;padding:26px}h1{font-size:24px;margin:0 0 10px}p{color:#596371;font-size:14px}select,audio{width:100%;margin:8px 0 14px}select{font:inherit;padding:10px;border:1px solid #d3d8df;border-radius:8px;background:white}.status{display:flex;gap:24px;flex-wrap:wrap;margin:12px 0}.status strong{font-size:21px}.meter{height:6px;background:#e5e8ec;border-radius:4px;overflow:hidden}.meter i{display:block;height:100%;width:0;background:#376bc4}small{color:#5e6877}.times{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px}button{padding:6px 12px;border:1px solid #d6dce5;background:white;border-radius:7px;cursor:pointer}a{color:#305f9f}</style>
<main><h1>怠速状态衔接</h1><p>启动 → 怠速 → 补油 → 回落 → 熄火，8 秒。先听新旧路径，再跳到回落处比较。</p>
<label for="mode">试听声音</label><select id="mode"><option value="candidate">启用候选怠速</option><option value="original">原有声音路径</option><option value="idle_solo">只听候选怠速分支</option></select>
<audio id="player" controls preload="metadata"></audio><small id="notice" role="status">正在准备音频…</small>
<div class="status"><div><small>工程转速</small><br><strong id="rpm">0 RPM</strong></div><div><small>当前状态</small><br><strong id="state">启动</strong></div><div><small>候选怠速占比</small><br><strong id="weight">0%</strong></div></div><div class="meter"><i id="fill"></i></div>
<div class="times"><button data-time="0">从启动听</button><button data-time="1.05">稳定怠速</button><button data-time="1.9">补油交接</button><button data-time="4.2">回落交接</button></div>
<p>本页用于检查音量与切换连续性。两端来自 F2 LP-610 尾排与 A Performante 素材，尚未做同一车型的转速标定。工程转速由当前控制程序产生。</p>
<p>三条使用同一主音量；候选怠速使用一次固定的声源电平校准。页面没有新增房间处理。</p>
<small><a href="../../idle_modal_v1/review2/index.html">返回固定怠速音色对照</a> · 请暂停其他发声窗口。</small></main>
<script>
const player=document.querySelector('#player'),mode=document.querySelector('#mode'),notice=document.querySelector('#notice'),buttons=[...document.querySelectorAll('[data-time]')];let data=[],revision=0;const audioURLs=new Map();
const life=['熄火','通电','起动机','接火','运行','熄火回落'],op=['怠速','空挡补油','加速','巡航','收油','换挡切扭','换挡恢复','降挡补油'];
function update(){if(!data.length)return;const r=data[Math.min(data.length-1,Math.floor(player.currentTime/.005))],w=mode.value==='original'?0:r[3];document.querySelector('#rpm').textContent=Math.round(r[0])+' RPM';document.querySelector('#state').textContent=r[1]===4?op[r[2]]:life[r[1]];document.querySelector('#weight').textContent=Math.round(100*w)+'%';document.querySelector('#fill').style.width=(100*w)+'%';}
fetch('state.json').then(r=>{if(!r.ok)throw Error('state');return r.json();}).then(rows=>{data=rows;update();}).catch(()=>{notice.textContent='状态读取失败，请刷新。';});
function sourceURL(name){if(!audioURLs.has(name))audioURLs.set(name,fetch(name+'.wav').then(r=>{if(!r.ok)throw Error('audio');return r.blob();}).then(blob=>URL.createObjectURL(blob)));return audioURLs.get(name);}
async function setSource(at,playing){const id=++revision,name=mode.value;player.pause();buttons.forEach(b=>b.disabled=true);notice.textContent='正在准备音频…';try{const url=await sourceURL(name);if(id!==revision)return;player.addEventListener('loadedmetadata',()=>{if(id!==revision)return;player.currentTime=Math.min(at,player.duration||at);buttons.forEach(b=>b.disabled=false);notice.textContent=name==='idle_solo'?'独奏仅在怠速分支进入时发声。':'';update();if(playing)player.play().catch(()=>{});},{once:true});player.src=url;player.load();}catch{if(id===revision)notice.textContent='音频读取失败，请刷新。';}}
mode.addEventListener('change',()=>setSource(player.currentTime,!player.paused));
buttons.forEach(button=>button.addEventListener('click',()=>{player.currentTime=Number(button.dataset.time);update();}));
window.addEventListener('pagehide',()=>{for(const promise of audioURLs.values())promise.then(url=>URL.revokeObjectURL(url)).catch(()=>{});});setSource(0,false);
player.addEventListener('timeupdate',update);player.addEventListener('seeked',update);
</script></html>'''
(a.out/'index.html').write_text(page,encoding='utf-8',newline='\n')
files={path.name:sha(path) for path in a.out.iterdir() if path.is_file()}
result=dict(result='state_transition_preview_prepared_not_listening_accepted',input_report_sha256=sha(a.input/'report.json'),
    level_gain=r['level_gain'],master_gain=.25,source_timbre_refitted=False,files=files,player_count=1,
    native_UI_or_default_changed=False,whole_vehicle_RPM_calibration=False)
(a.out/'report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=result['result'],page=str(a.out/'index.html'))),flush=True)
