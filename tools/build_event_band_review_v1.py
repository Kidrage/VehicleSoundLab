"""A scoped exhaust increment: original context, actual C and editable project."""
import argparse
import base64
import html
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--project-root',type=Path,default=Path('E:/VehicleSoundLab/designs/events'))
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from scipy import signal
    from author_event import author
    from event_authoring.audio import read,sha
    from event_authoring.measure import spectrum
    from event_authoring.model import synth
    from event_authoring.native import Renderer,controls
    from event_designer.workspace import EventWorkspace
    repo=Path(__file__).resolve().parents[1];jobfile=repo/'examples/event_authoring/A_tailpipe_single_band.job.json'
    job=json.loads(jobfile.read_text(encoding='utf-8'));source=Path(job['source'])
    approvals=json.loads(Path('E:/VehicleSoundLab/references/approval_manifest.json').read_text(encoding='utf-8'))
    manifest=json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    approved=next(row for row in approvals if row['id']=='A') if isinstance(approvals,list) else None
    assert approved and approved['approved'] and sha(source)==manifest['sources']['A']['master_sha256']
    fit_result=author(jobfile,a.output/'analysis')
    if fit_result.get('status')=='analysis_only':raise ValueError('Selected candidate did not meet declared-scope contrast')
    document=json.loads((a.output/'analysis/profile.json').read_text(encoding='utf-8'))
    renderer=Renderer(repo);values=controls(dict(seconds=.6))
    x,render_report=renderer.render(document['parameters'],job['kind'],values)
    expected=synth(document['parameters'],seconds=.6).astype(np.float32)
    expected=np.pad(expected,(0,len(x)-len(expected)))
    error=float(np.max(abs(x.astype(float)-expected)));assert error<2e-7
    sf.write(a.output/'synthesis.wav',x,48000,subtype='FLOAT')
    first,last=334.6,336.2;context,sr,provenance=read(source,first,last)
    placed=np.zeros((len(context),2));offset=round((job['seconds'][0]-first)*sr)
    placed[offset:offset+len(x)]=x[:,None]
    lo,hi=job['analysis_scope']['low_hz'],job['analysis_scope']['high_hz']
    sos=signal.butter(4,[lo,hi],btype='bandpass',fs=sr,output='sos')
    # Filter the continuous original before cropping: listening filter has no
    # fresh zero-state at the selected event boundary. It is NOT separation.
    preroll,_,_=read(source,first-.5,last)
    filtered=signal.sosfilt(sos,preroll,axis=0)[24000:]
    filtered_c=signal.sosfilt(sos,placed,axis=0)
    tracks=[('context','原声语境 · 全频',context),('band','原声语境 · 1.2–14 kHz监听',filtered),
            ('candidate','C候选 · 单次局部短声',placed),('candidate_band','C候选 · 同频带监听',filtered_c)]
    for key,label,audio in tracks:sf.write(a.output/(key+'.wav'),audio*.25,sr,subtype='FLOAT')
    # An editable event project uses exactly the same sample-addressed content.
    path=a.output/'context-original.wav';sf.write(path,context,sr,subtype='FLOAT')
    workspace=EventWorkspace(repo,a.project_root)
    project=workspace.create(dict(filename='A_tailpipe_334.6-336.2.wav',
        audio=base64.b64encode(path.read_bytes()).decode(),kind=job['kind'],viewpoint='exterior'))
    relative=[round(v-first,6) for v in job['seconds']];background=[round(v-first,6) for v in job['background_seconds']]
    project=workspace.analyze(dict(id=project['id'],name=job['name'],seconds=relative,background_seconds=background,
        analysis_scope=job['analysis_scope'],context=job['context'],gated=False))
    assert project['document']['parameters']==document['parameters']
    project=workspace.render(dict(id=project['id'],controls=values))
    rendered,_=sf.read(workspace.root/project['id']/project['last_version']/'synthesis.wav',dtype='float32')
    assert np.array_equal(x,rendered) and project['reference_matches_model']
    shutil.copytree(workspace.root/project['id'],a.output/'editable-project')
    metrics=[]
    event,_,_=read(source,*job['seconds']);f,power=spectrum(event)
    duration=round((job['seconds'][1]-job['seconds'][0])*sr)
    cf,cp=spectrum(x[:duration,None]);cp=np.interp(f,cf,cp)
    for band in document['observation']['bands']:
        lower,upper=band['hz'];mask=(f>=lower)&(f<upper);df=f[1]-f[0]
        metrics.append(dict(hz=band['hz'],reference_event_power=float(power[mask].sum()*df),
            estimated_positive_excess_power=band['excess_power'],generated_power=float(cp[mask].sum()*df),
            decay_fitted=band['decay_fitted'],decay_seconds=band['decay_seconds']))
    report=dict(schema='vsl.event-band-review/1',source=provenance,source_job=job,
        fit_result=fit_result,renderer=render_report,independent_C_error=error,
        editable_project=str(workspace.root/project['id']),editable_project_pcm_exact=True,metrics=metrics,
        analysis_scope=job['analysis_scope'],physical_identity_confirmed=False,hearing_accepted=False,
        global_event_bank_changed=False,monitor_gain=.25,
        limitations=['The crop is one acoustic burst within a cluster; no ECU or overrun evidence confirms afterfire.',
            'Original reference retains continuous engine/background; subtraction estimates only a spectral increment.',
            'No LF body was fitted and this candidate is not a complete event or full-band engine reconstruction.',
            'A single short event has limited frequency/decay resolution; fallback decays remain explicitly marked.',
            'Listening filter is shared for comparison only; no room, compressor or individual gain compensation.'])
    report['files']={path.name:sha(path) for path in a.output.glob('*.wav')}
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    buttons=''.join('<button data-src="'+key+'.wav">'+label+'</button>' for key,label,_ in tracks)
    contrast=document['observation'];escape=html.escape
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>尾排局部短声 · 频带提参 V1</title><style>body{margin:0;background:#101714;color:#edf3e8;font:16px/1.7 system-ui}main{max-width:900px;margin:44px auto;padding:0 22px}h1{font-size:29px;line-height:1.35}p{color:#b6c3ba}section{background:#1b2420;padding:22px;border-radius:14px;margin:24px 0}button,a{font:inherit}button{display:block;width:100%;text-align:left;background:#28352d;border:1px solid #50644e;color:#edf3e8;padding:12px 16px;margin:8px 0;border-radius:7px;cursor:pointer}button[aria-pressed=true]{background:#badc86;color:#172112}audio{width:100%;margin:18px 0}a{color:#badc86}small{color:#b6c3ba}img{max-width:100%;border-radius:8px}.warning{color:#e7c78b}</style>
<main><small>VEHICLE SOUND / 独立事件提参</small><h1>先辨认短声，再判断合成。</h1>
<p>A素材原时间334.6–336.2秒，尾排近录。此次只拟合335.265–335.365秒的一个局部峰，播放约0.67秒处。整组中其他短声未生成。</p>
<p class="warning">这是1.2–14 kHz补充候选，尚未确认是回火，也未替换车辆事件库。原声包含持续发动机和背景；C候选只生成局部增量，缺少低频部分，不能按完整发动机声对比。</p>
<section><strong id="label">原声语境 · 全频</strong><audio id="player" controls preload="metadata"></audio>'''+buttons+'''
<small>一个播放器，无自动播放。四条统一乘0.25，不做单独归一化、压缩或房间处理。频带监听是同一四阶带通，可能有滤波延时；C候选原生是单声道。</small></section>
<p>单次选区全频对比度 '''+f"{contrast['event_to_background_db']:+.2f}"+''' dB，指定频带对比度 '''+f"{contrast['scoped_event_to_background_db']:+.2f}"+''' dB。它说明有局部声学增量，不能证明真实机械成因。</p>
<p>对照顺序：原声全频确认短声，再比较同频带原声与C候选。重点判断尖锐起音、尾音和机械质感；候选有无低频厚度不在本次范围。</p>
<p><a href="editable-project/'''+project['last_version']+'''/parameters.json">可编辑参数JSON</a> · <a href="editable-project/'''+project['last_version']+'''/event-design.zip">C参数与试听包</a> · <a href="report.json">分析记录</a></p>
<p>独立事件工作台工程：'''+escape(project['id'])+'''。导入JSON后可调正弦模态、相位、衰减和噪声共振；运行时不播放原录音。</p>
</main><script src="app.js"></script></html>'''
    (a.output/'index.html').write_text(page,encoding='utf-8')
    shutil.copy2(repo/'tools/event_band_review_web_v1.js',a.output/'app.js')
    shutil.copy2(__file__,a.output/'executed_build.py')
    exact=a.output/'exact_sources';exact.mkdir()
    for path in [repo/'tools/author_event.py',*sorted((repo/'tools/event_authoring').glob('*.py')),
                 *sorted((repo/'tools/event_designer').glob('*.py'))]:
        target=exact/path.relative_to(repo/'tools');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    print(json.dumps(dict(result='built',output=str(a.output),project=project['id'],C_max_error=error,
        full_contrast_db=contrast['event_to_background_db'],scoped_contrast_db=contrast['scoped_event_to_background_db']),ensure_ascii=False))


if __name__=='__main__':main()
