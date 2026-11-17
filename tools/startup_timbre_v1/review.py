"""A single-player, fixed-gain comparison of actual native event and driving output."""
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_authoring.audio import sha
from event_authoring.native import Renderer
from event_designer.package import write_json


def build(repo,capture,output,projects):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    renderer=Renderer(repo);tracks=[]
    for name,label in [('original','原启动参数'),('candidate','频谱校准候选')]:
        folder=capture/name
        shutil.copy2(folder/'mix.wav',output/(name+'-mix.wav'))
        packed,sr=sf.read(folder/'native.wav',dtype='float32',always_2d=True)
        events=np.sum(packed[:,19:].astype(float),axis=1)*2**-.5
        sf.write(output/(name+'-events.wav'),events,sr,subtype='FLOAT')
        for suffix,title in [('mix','完整干声'),('events','独立事件')]:
            tracks.append(dict(file=name+'-'+suffix+'.wav',group='cycle',label=label+' · '+title))
    import json
    bank=json.loads((repo/'voices/events_v1/profiles.json').read_text(encoding='utf-8'))
    for row in projects['projects']:
        kind=row['kind'];folder=capture/'projects'/kind
        for filename,newname in [('preview.wav',kind+'-new.wav'),('reference-monitor.wav',kind+'-reference.wav')]:
            shutil.copy2(folder/filename,output/newname)
        old,_=renderer.render(bank['profiles'][kind]['parameters'],kind,row['controls'])
        sf.write(output/(kind+'-old.wav'),old*.25,48000,subtype='FLOAT')
        for suffix,title in [('old','原参数'),('new','频谱校准候选'),('reference','原录音选区')]:
            tracks.append(dict(file=kind+'-'+suffix+'.wav',group=kind,label=('早期纹理' if kind=='crank' else '接火补充')+' · '+title))
        shutil.copytree(folder,output/(kind+'-parameters'))
    x,sr=sf.read(projects['context'],always_2d=True)
    sf.write(output/'source.wav',x*.25,sr,subtype='FLOAT')
    tracks.append(dict(file='source.wav',group='source',label='A 原声启动上下文 · 35–40.5秒'))
    for source,dest in [(capture/'candidate/lifecycle.vsltake.json','candidate.vsltake.json'),
                        (capture/'startup-candidate.recipe.json','candidate.recipe.json'),
                        (capture/'candidate/telemetry.csv','telemetry.csv')]:shutil.copy2(source,output/dest)
    shutil.copy2(repo/'tools/exhaust_return_review_web_v1.js',output/'app.js')
    buttons=lambda rows:''.join(f'<button data-src="{r["file"]}" data-group="{r["group"]}">{r["label"]}</button>' for r in rows)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>启动音色 · 素材频谱校准</title><style>body{margin:0;background:#f2f4f7;color:#172338;font:16px/1.7 system-ui}main{max-width:880px;padding:24px;margin:auto}h1{font-size:28px}section{background:white;border-radius:12px;padding:22px;margin:22px 0}button{display:block;width:100%;padding:12px;margin:10px 0;text-align:left;border:1px solid #bbc6d6;border-radius:6px;background:#f2f4f7;font:inherit;color:#172338;cursor:pointer}button[aria-pressed=true]{background:#215fcd;color:white}audio{width:100%}a{color:#215fcd}p,small{overflow-wrap:anywhere}.transport{position:sticky;top:0;z-index:1;box-shadow:0 2px 12px #17233818}.note{color:#667387}</style>
<main><small>VEHICLE SOUND / STARTUP TIMBRE</small><h1>只改变启动事件，比较完整流程。</h1>
<p>此次针对启动候选高频噪声偏多：从同一A素材联合校准模态／噪声电平，并只在程序噪声支路加入10 kHz高切。主DNA、低频、35%共振细节、怠速、驾驶轨迹与收油局部短声保持相同。没有新增房间处理。</p>
<section class="transport"><strong id="label"></strong><audio controls preload="metadata"></audio><small>一个播放器，无自动播放；同组切换保留进度。所有试听固定增益0.25，无分别归一化或限幅。</small></section>
<section><h2>完整 C 系统 · 32秒</h2><p>0.35秒启动，2.5秒起步，15.5秒收油，18秒制动，27秒停车怠速，29.5秒熄火。先比较前3秒，再听完整流程。</p>'''+buttons(tracks[:4])+'''
<small>两版前19个连续分轨逐样本相同；3秒后全部23通道相同。独立事件包含未确认物理身份的E局部短声，不代表完整回火已完成。</small></section>
<section><h2>单独检查启动音色</h2><p>原录音为混合车内声，不是分离出的起动机或接火。单独候选由实际C事件核生成；门控早期纹理在0.47秒释放。切到另一组选区会从头开始。</p>'''+buttons(tracks[4:])+'''
<small>原声短选区时长与合成试听长度不同；仅供音色参考，不进行逐样本对齐。C完整启动轨迹由唯一驾驶器产生，仍是工程动作参数，未标定原车RPM。</small></section>
<p><a href="candidate.recipe.json" download>完整候选配方</a> · <a href="candidate.vsltake.json" download>可回放驾驶行程</a> · <a href="telemetry.csv" download>实际C转速／状态表</a></p>
<p><a href="crank-parameters/event-design.zip" download>早期纹理参数包</a> · <a href="catch-parameters/event-design.zip" download>接火参数包</a> · <a href="report.json">来源与核查</a></p>
<p class="note">工作台“独立事件”页可编辑噪声高切、各模态与频带，再导出JSON；独立控制窗口V6停止监听后导入，下次启动采用。新候选未替换正式音色库，仍需听音确认。</p></main><script src="app.js"></script></html>'''
    (output/'index.html').write_text(page,encoding='utf-8')
    write_json(output/'report.json',dict(schema='vsl.startup-timbre-review/1',tracks=tracks,
        monitor_gain=.25,independent_normalization=False,spatial_processing=False,
        source_context_original_seconds=[35,40.5],projects=[dict(id=r['id'],kind=r['kind']) for r in projects['projects']],
        files={p.name:sha(p) for p in output.iterdir() if p.is_file()},
        timbre_accepted=False,goal_complete=False))
