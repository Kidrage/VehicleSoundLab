"""Editable local exhaust-return candidate and its actual C lift-trigger demo."""
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from scipy import signal
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from event_authoring.audio import read,sha
    from event_authoring.native import controls
    from event_designer.workspace import EventWorkspace
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller import take,recipe
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab');bridge=Bridge(repo)
    job=json.loads((repo/'examples/event_authoring/E_exhaust_return_band.job.json').read_text(encoding='utf-8'))
    fit=data/'references/analysis/exhaust_return_v1/fit1';doc=json.loads((fit/'profile.json').read_text(encoding='utf-8'))
    assert doc['source_job']==job and doc['physical_identity_confirmed'] is False
    shutil.copytree(fit,a.output/'analysis')
    source=Path(job['source']);manifest=json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    assert sha(source)==manifest['sources']['E']['master_sha256']
    approved=json.loads((data/'references/approval_manifest.json').read_text(encoding='utf-8'))
    assert any(r['id']=='E' and r['approved'] for r in approved)
    context,sr,origin=read(source,12.6,14.)
    sf.write(a.output/'context-original.wav',context,sr,subtype='FLOAT')
    workspace=EventWorkspace(repo,data/'designs/events')
    project=workspace.create(dict(filename='E_exhaust_return_12.6-14.0.wav',
        audio=base64.b64encode((a.output/'context-original.wav').read_bytes()).decode(),kind='afterfire',viewpoint='exterior'))
    project=workspace.analyze(dict(id=project['id'],name=job['name'],seconds=[.685,.785],
        background_seconds=[.36,.56],analysis_scope=job['analysis_scope'],context=job['context'],gated=False))
    assert project['document']['parameters']==doc['parameters']
    project=workspace.render(dict(id=project['id'],controls=controls(dict(seconds=.6))))
    assert project['reference_matches_model']
    c,_=sf.read(workspace.root/project['id']/project['last_version']/'synthesis.wav',dtype='float32')
    generated=np.zeros(len(context));at=round(.685*sr);generated[at:at+len(c)]=c
    sos=signal.butter(4,[1200,14000],btype='bandpass',fs=sr,output='sos')
    band=signal.sosfilt(sos,context,axis=0)
    sf.write(a.output/'reference.wav',context*.25,sr,subtype='FLOAT')
    sf.write(a.output/'reference_band.wav',band*.25,sr,subtype='FLOAT')
    sf.write(a.output/'candidate.wav',generated*.25,sr,subtype='FLOAT')
    shutil.copytree(workspace.root/project['id'],a.output/'editable-project')
    take.save(a.output/'event-profile.json',doc)
    # Same accepted main recipe/seed/driver in both renders. Only the AFTERFIRE
    # level changes; silent event voices keep identical notices/scheduling.
    selection=next(r['id'] for r in bridge.catalog if r['key']=='v10-moving35')
    control=bridge.initial(selection)[0]
    control.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7,gain=.25,backfire=1)
    control['events'].update(enabled=1,gain=.5,pitch=1.,decay=1.,texture=1.,manual_sequence=0)
    control['events']['levels']=[0.,0.,0.,1.,0.,0.,0.]
    startup=deepcopy(bridge.startup_defaults);overrides={'afterfire':doc}
    on=take.create(bridge,selection,control,overrides,startup);on['frames']=8*48000
    for seconds,changes in ((1.7,dict(throttle=.65)),(3.7,dict(throttle=0.)),
                            (5.,dict(throttle=.45)),(6.5,dict(throttle=0.))):
        control.update(changes);take.append(on,round(seconds*48000),control)
    off=deepcopy(on)
    for ctl in [off['initial']]+[e['control'] for e in off['events']]:ctl['events']['levels'][3]=0.
    captures={};offsets=np.cumsum([0]+[r['channels'] for r in bridge.stems]);event_offset=offsets[12]
    for name,value in (('off',off),('on',on)):
        parts=[];native=[];rows=[];notices=[];index=0
        with Engine(bridge,selection,overrides,startup) as engine:
            engine.set(value['initial'])
            while engine.frame<value['frames']:
                pcm,index=take.replay_block(engine,value,index,240)
                parts.append(np.frombuffer(pcm,dtype='<f4').reshape(-1,2).copy())
                native.append(np.ctypeslib.as_array(engine.stems)[:240*bridge.channels()].reshape(240,-1).copy())
                rows.append(engine.state());notices.extend(engine.last_events)
        value['source_events']=notices
        x=np.concatenate(parts);stems=np.concatenate(native)
        captures[name]=dict(mix=x,stems=stems,rows=rows,notices=notices)
        sf.write(a.output/('drive_'+name+'.wav'),x,48000,subtype='FLOAT')
        take.save(a.output/('drive_'+name+'.vsltake.json'),value)
    assert np.array_equal(captures['on']['stems'][:,:event_offset],captures['off']['stems'][:,:event_offset])
    assert captures['on']['notices']==captures['off']['notices']
    event_mono=captures['on']['stems'][:,event_offset:].sum(axis=1)*2**-.5
    event_mix=np.column_stack((event_mono,event_mono))
    error=float(np.max(abs(captures['on']['mix'].astype(float)-captures['off']['mix']-event_mix)))
    assert error<2e-7,error
    sf.write(a.output/'drive_events.wav',event_mix,48000,subtype='FLOAT')
    starts=[n for n in on['source_events'] if n['type']==3 and n['action']==1]
    assert len(starts)>=2 and captures['on']['rows'][-1]['overruns']==2,starts
    assert all(n['frame']==n['requested_frame'] for n in starts)
    final=captures['on']['rows'][-1]
    assert final['event_peak']<=4 and final['event_overflow']==final['event_log_lost']==final['event_rejected']==0
    preset=recipe.create(bridge,selection,on['initial'],'踏板驾驶',overrides,startup)
    take.save(a.output/'controller-preset.json',preset)
    take.save(a.output/'drive-telemetry.json',captures['on']['rows'])
    take.save(a.output/'drive-events.json',on['source_events'])
    fig,axes=plt.subplots(2,1,figsize=(10,4.5),layout='constrained',sharex=True)
    times=[r['frame']/48000 for r in captures['on']['rows']]
    axes[0].plot(times,[r['rpm'] for r in captures['on']['rows']]);axes[0].set(ylabel='Virtual RPM')
    axes[1].plot(np.arange(len(event_mono))/48000,event_mono,lw=.5);axes[1].set(ylabel='Event monitor / FS',xlabel='C generated time (s)')
    for ax in axes:
        ax.grid(alpha=.2)
        for n in starts:ax.axvline(n['frame']/48000,color='#a64b2a',ls=':',lw=.7)
    fig.savefig(a.output/'drive.png',dpi=150);plt.close(fig)
    report=dict(schema='vsl.exhaust-return-review/1',goal_complete=False,timbre_accepted=False,physical_identity_confirmed=False,
        bridge_sha256=bridge.sha256,voices_sha256=bridge.voices_sha256,source=origin,source_job=job,
        project=str(workspace.root/project['id']),editable_project_matches_cli=True,
        full_contrast_db=doc['observation']['event_to_background_db'],scoped_contrast_db=doc['observation']['scoped_event_to_background_db'],
        generation=dict(frames=on['frames'],selection=selection,pedal_only=True,overruns=final['overruns'],starts=starts,
            non_event_stems_exact=True,notices_exact_with_level_zero=True,mix_difference_reconstruction_error=error,
            event_monitor_peak=float(abs(event_mono).max()),final_state=final),
        global_bank_changed=False,runtime_uses_recording=False,
        files={p.name:sha(p) for p in a.output.glob('*.wav')},
        limitations=['Only1.2..14kHz exhaust-return acoustic supplement, not confirmed/full-band afterfire.',
            'C neutral-rev pedals demonstrate triggering, not a measured reproduction of E footage.',
            'Candidate modes/noise share a short-envelope model; spectral fit does not prove transient fidelity/naturalness.',
            'Local afterfire slot override is explicit; compiled global event bank remains unchanged.'])
    take.save(a.output/'report.json',report)
    buttons=''.join(f'<button data-src="{file}" data-group="{group}">{label}</button>' for file,group,label in (
        ('reference.wav','reference','E 原声 · 补油后短声'),('reference_band.wav','reference','E 原声 · 只听1.2–14 kHz'),
        ('candidate.wav','reference','实际 C · 中高频短声候选'),('drive_off.wav','drive','C 空挡补油 · 短声电平0'),
        ('drive_on.wav','drive','C 空挡补油 · 短声电平100%'),('drive_events.wav','drive','只听 C 事件分轨')))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>尾排收油短声 · V1</title><style>body{margin:0;background:#f2f4f7;color:#172338;font:16px/1.7 system-ui}main{max-width:880px;margin:auto;padding:24px}h1{font-size:28px}section{background:white;padding:22px;border-radius:12px;margin:22px 0}button{display:block;width:100%;font:inherit;text-align:left;padding:12px;border:1px solid #bbc6d6;background:#f2f4f7;color:#172338;border-radius:6px;margin:10px 0;cursor:pointer}button[aria-pressed=true]{background:#215fcd;color:white}audio,img{width:100%}a{color:#215fcd}p,small{overflow-wrap:anywhere}.note{color:#667387}</style>
<main><small>VEHICLE SOUND / 本地素材 → 事件参数 → 实际C触发</small><h1>尾排短声，接进收油动作。</h1>
<p>E驻车尾排画面12.6–14.0秒；约0.71秒处有一次宽频短声，前方谐波声线正在回落。此候选只拟合1.2–14kHz增量，低频未还原，物理回火身份与听感仍待确认。</p>
<section><strong id="label"></strong><audio controls preload="metadata"></audio>'''+buttons+'''
<small>一个播放器，无自动播放。同组切换保留进度，换组从头。参考/C单次统一乘0.25；车辆C对照共用输出0.25，只有事件电平不同，无房间／压缩／逐版归一化。</small></section>
<img src="drive.png" alt="实际C空挡补油转速与事件分轨；两次收油触发独立短声">
<p>8秒C演示为启动、两次空挡补油和收油；RPM由同一驾驶器计算。两版持续DNA、低频及细节逐样本相同，差值来自独立事件分轨。它展示控制链，不是按视频复制转速或循环原片段。</p>
<p><a href="controller-preset.json">独立控制窗口配方JSON</a> · <a href="drive_on.vsltake.json">8秒控制行程</a> · <a href="event-profile.json">事件参数JSON</a> · <a href="report.json">来源与验证</a></p>
<p>独立窗口V4：停止监听后载入“控制窗口配方”，即可用油门／W键补油，再松开触发；也可回放8秒行程。事件页可调电平、音高、时长和纹理，或在工作台事件页导入参数继续编辑。</p>
<p class="note">原声包含持续发动机与现场背景，C单次只生成局部补充；起音和尾音尚未通过听评。此工程覆盖不会修改编译事件库，当前不是正式的全频回火预设。</p></main><script src="app.js"></script></html>'''
    (a.output/'index.html').write_text(page,encoding='utf-8')
    shutil.copy2(repo/'tools/exhaust_return_review_web_v1.js',a.output/'app.js')
    shutil.copy2(__file__,a.output/'executed_build.py')
    exact=a.output/'exact_sources';exact.mkdir()
    for path in [*sorted((repo/'tools/event_authoring').glob('*.py')),*sorted((repo/'tools/vehicle_controller').glob('*.py'))]:
        dst=exact/path.relative_to(repo/'tools');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dst)
    print(json.dumps(dict(output=str(a.output),project=report['project'],generation=report['generation']),ensure_ascii=False))


if __name__=='__main__':main()
