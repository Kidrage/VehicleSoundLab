"""Native-C 1150/2000 RPM startup action comparison, not a new timbre model."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller import take
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab');bridge=Bridge(repo)
    curves=[];tracks=[]
    for name,peak in (('default',1150.),('flare2000',2000.)):
        response=dict(bridge.startup_defaults,flare_rpm=peak)
        control=bridge.initial(0)[0]
        control.update(mode=1,ignition=0,start_id=0,gear=0,throttle=0.,brake=.65,gain=.25)
        control['events']['enabled']=1
        value=take.create(bridge,0,control,startup_response=response);value['frames']=48000*6
        for seconds,changes in ((.35,dict(ignition=1,start_id=1)),(4.8,dict(ignition=0))):
            control.update(changes);take.append(value,round(seconds*48000),control)
        parts=[];rows=[];index=0;notices=[]
        with Engine(bridge,0,startup_response=response) as engine:
            engine.set(value['initial'])
            while engine.frame<value['frames']:
                pcm,index=take.replay_block(engine,value,index,240)
                parts.append(pcm);rows.append(engine.state());notices.extend(engine.last_events)
        value['source_events']=notices
        x=np.frombuffer(b''.join(parts),dtype='<f4').reshape(-1,2)
        sf.write(a.output/(name+'.wav'),x,48000,subtype='FLOAT')
        take.save(a.output/(name+'.vsltake.json'),value);take.save(a.output/(name+'.telemetry.json'),rows)
        curves.append((name,rows));tracks.append(dict(file=name+'.wav',response=response,
            peak_rpm=max(row['rpm'] for row in rows),gain=.25,sha256=sha(a.output/(name+'.wav'))))
    sources=json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    source=data/sources['sources']['A']['master']
    assert sha(source)==sources['sources']['A']['master_sha256']
    approvals=json.loads((data/'references/approval_manifest.json').read_text(encoding='utf-8'))
    assert any(r['id']=='A' and r['approved'] for r in approvals)
    with sf.SoundFile(source) as stream:
        sr=stream.samplerate;stream.seek(round(35.5*sr));original=stream.read(round(6*sr),dtype='float32',always_2d=True)
    sf.write(a.output/'reference.wav',original*.25,sr,subtype='FLOAT')
    fig,ax=plt.subplots(figsize=(10,3.4),layout='constrained')
    for name,rows in curves:
        ax.plot([row['frame']/48000 for row in rows],[row['rpm'] for row in rows],label=name)
    ax.axvline(.35,color='#777777',ls=':',lw=1);ax.axvline(4.8,color='#777777',ls=':',lw=1)
    ax.set(xlabel='Generated audio time (s)',ylabel='Virtual RPM',ylim=(0,2200));ax.grid(alpha=.2);ax.legend()
    fig.savefig(a.output/'rpm.png',dpi=150);plt.close(fig)
    shutil.copy2(repo/'tools/event_band_review_web_v1.js',a.output/'app.js')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>启动响应 · V1</title><style>body{margin:0;background:#f2f4f7;color:#172338;font:16px/1.7 system-ui}main{max-width:880px;padding:24px;margin:auto}h1{font-size:28px}section{background:white;border-radius:12px;padding:22px;margin:22px 0}button{display:block;width:100%;padding:12px;margin:10px 0;text-align:left;border:1px solid #bbc6d6;border-radius:6px;background:#f2f4f7;font:inherit;color:#172338;cursor:pointer}button[aria-pressed=true]{background:#215fcd;color:white}audio,img{width:100%}a{color:#215fcd}p,small{overflow-wrap:anywhere}.note{color:#667387}</style>
<main><small>VEHICLE SOUND / 启动与停机响应</small><h1>同一声源，改变启动动作。</h1>
<p>比较两条实际 C 生成：0.35秒启动，4.8秒熄火。只把冲转峰值由1150改为2000 RPM，其他参数、种子和增益相同。此页用于核对动作控制，并未生成新的启动声纹。</p>
<section><strong id="label">默认启动 · 1150 RPM</strong><audio controls preload="metadata"></audio>
<button data-src="default.wav">默认启动 · 1150 RPM</button><button data-src="flare2000.wav">工程对照 · 2000 RPM</button>
<button data-src="reference.wav">A 原声短参考 · 35.5–41.5秒</button>
<small>单播放器，无自动播放。两条 C 共用输出增益0.25；原声也只乘0.25，没有分别归一化、房间或压缩。原声与C未测量音画／显示延迟，不作逐时刻对齐。</small></section>
<img src="rpm.png" alt="两条C实际虚拟转速轨迹，2000RPM对照的冲转峰值更高">
<p class="note">2000 RPM落在A仪表粗读高点1800–2500范围内，仅是工程候选，不代表已标定实车转速或声学阶次。当前全状态DNA仍有覆盖缺口，不能把拉高现有声源等同还原真实接火音色。独立事件仍沿用未经认可的A混合座舱拖转／接火候选，回火尚未编入正式库。</p>
<p><a href="default.vsltake.json">默认行程</a> · <a href="flare2000.vsltake.json">2000 RPM行程</a> · <a href="report.json">参数与记录</a></p>
<p>独立控制窗口V4：驾驶页 → 启动与停机响应。九项参数可编辑，停止监听后应用，随配方与行程保存。</p></main><script src="app.js"></script></html>'''
    (a.output/'index.html').write_text(page,encoding='utf-8')
    report=dict(schema='vsl.startup-response-review/1',bridge_sha256=bridge.sha256,voices_sha256=bridge.voices_sha256,
        goal_complete=False,timbre_accepted=False,new_timbre_model=False,tracks=tracks,
        reference=dict(source=str(source),source_sha256=sha(source),seconds=[35.5,41.5],gain=.25),
        files={p.name:sha(p) for p in a.output.iterdir() if p.is_file()})
    take.save(a.output/'report.json',report)
    shutil.copy2(__file__,a.output/'executed_build.py')
    print(json.dumps(dict(output=str(a.output),tracks=tracks,goal_complete=False),ensure_ascii=False))


if __name__=='__main__':main()
