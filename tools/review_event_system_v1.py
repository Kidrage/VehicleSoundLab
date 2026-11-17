"""Publish one-player source/C audition, with explicit candidate/action labels."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--checks',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from event_authoring.audio import read,sha
    from vehicle_controller.native import Bridge,Engine
    repo=Path(__file__).resolve().parents[1];bridge=Bridge(repo);rows=[]
    for key,name in [('crank','启动早期纹理'),('catch','接火补充')]:
        model=bridge.event_profiles[key];x,sr,_=read(model['provenance']['path'],*model['provenance']['source_seconds'])
        filename=key+'_reference.wav';sf.write(a.output/filename,x*.25,sr,subtype='FLOAT')
        rows.append(dict(name=name+' · 原声混合片段',file=filename,kind='reference'))
        filename=key+'_c.wav';shutil.copy2(a.checks/(key+'_c_review.wav'),a.output/filename)
        rows.append(dict(name=name+' · C纯合成候选',file=filename,kind='synthesis'))
    x,sr,prov=read(Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav'),33,40)
    sf.write(a.output/'start_context.wav',x*.25,sr,subtype='FLOAT')
    rows.append(dict(name='A原声启动语境 · 33–40秒',file='start_context.wav',kind='context'))
    for enabled,name in [(0,'原持续声源链'),(1,'新启动事件＋持续声源')]:
        control,_=bridge.initial(0);control.update(ignition=1,start_id=1,mode=0,rpm=850,load=.2)
        control['events']['enabled']=enabled;control['events']['gain']=.35;parts=[];notices=[]
        with Engine(bridge,0) as engine:
            engine.set(control)
            for _ in range(320):
                parts.append(engine.process(480));notices.extend(deepcopy(engine.last_events))
            state=engine.state()
        data=np.frombuffer(b''.join(parts),dtype='<f4').reshape(-1,2)*.25
        filename='full_start_'+str(enabled)+'.wav';sf.write(a.output/filename,data,48000,subtype='FLOAT')
        rows.append(dict(name=name+' · 工程启动轨迹3.2秒',file=filename,kind='lifecycle',
            control=control,final_state=state,notices=notices,peak=float(np.max(abs(data)))))
    items=json.dumps(rows,ensure_ascii=False)
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>独立事件 · 启动候选 V1</title><style>body{font:16px/1.7 system-ui;background:#f2f4f7;color:#172338;max-width:900px;margin:40px auto;padding:0 22px}h1{font-size:27px}p{color:#566477}section{background:white;border:1px solid #d8dfe8;border-radius:12px;padding:22px;margin:20px 0}audio{width:100%;margin:16px 0}button{font:inherit;padding:10px 14px;margin:5px;border:1px solid #c6d0df;background:white;border-radius:7px;color:#172338;cursor:pointer}button[aria-pressed=true]{background:#225fca;color:white}small{color:#667387}</style>
<h1>独立事件 · 启动候选 V1</h1><p>本轮先试听启动早期纹理与接火补充。它们来自A的车内混合录音，尚未分离为物理起动机或独立点火声，也未获得音色验收。</p>
<section><strong id="label"></strong><audio id="player" controls preload="metadata"></audio><div id="choices"></div><small>同一播放器，切换互斥；文件统一乘0.25，无逐条响度补偿，无房间处理。完整链保留原输出电平与事件35%设置。</small></section>
<p>先比较两组短片段的音色，再听完整启动链。完整启动采用现有工程RPM轨迹，与原录音的动作时长或实测RPM并未对齐；原声语境独立保留，避免把二者当成同步复现。</p>
<p>本地“VEHICLE SOUND · 驾驶与声源控制 V2”的“独立事件”页可调电平、音高、衰减、纹理，并单次试听。回火和其他缺少独立素材的类型暂时禁用。</p>
<script>const rows=ROWS,player=document.getElementById('player'),label=document.getElementById('label');
function choose(i){const running=!player.paused;player.pause();player.src=rows[i].file;label.textContent=rows[i].name;document.querySelectorAll('button').forEach((b,k)=>b.setAttribute('aria-pressed',k===i));player.load();if(running)player.play().catch(()=>{});}
rows.forEach((r,i)=>{const b=document.createElement('button');b.textContent=r.name;b.onclick=()=>choose(i);document.getElementById('choices').append(b)});choose(0);</script></html>'''.replace('ROWS',items)
    (a.output/'index.html').write_text(html,encoding='utf-8');shutil.copy2(__file__,a.output/'executed_review.py')
    report=dict(schema='vsl.event-review/1',bridge_sha256=bridge.sha256,event_bank_sha256=bridge.event_bank_sha256,
        gain=.25,clips=rows,start_context=prov,hearing_accepted=False,
        files={path.name:sha(path) for path in a.output.iterdir() if path.is_file()})
    (a.output/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(output=str(a.output),clips=len(rows),hearing_accepted=False)))


if __name__=='__main__':main()
