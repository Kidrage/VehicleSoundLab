"""Show the original-V4 tail defect and actual V5 cancellation with one player."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fixed',type=Path);a=p.parse_args()
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from event_authoring.audio import read,sha
    data=Path('E:/VehicleSoundLab');repo=Path(__file__).resolve().parents[1]
    evidence=data/'renders/startup_abort_v1';old=evidence/'baseline1';new=a.fixed or evidence/'fixed3'
    a.output.mkdir(parents=True,exist_ok=False)
    reports={name:json.loads((folder/'report.json').read_text(encoding='utf-8')) for name,folder in (('old',old),('new',new))}
    assert reports['old']['has_event_tail_after_OFF'] and not reports['new']['has_event_tail_after_OFF']
    for label,folder in (('old',old),('new',new)):
        for name in ('mix','events'):shutil.copy2(folder/(name+'.wav'),a.output/(label+'-'+name+'.wav'))
    reference,sr,origin=read(data/'references/clean/A_decoded_float.wav',35.,40.5)
    sf.write(a.output/'A-reference.wav',reference*.25,sr,subtype='FLOAT')
    fig,ax=plt.subplots(figsize=(10,3.5),layout='constrained')
    for label,color in (('old','#9b6a47'),('new','#2264c9')):
        x,sr=sf.read(a.output/(label+'-events.wav'));rms=np.sqrt(np.mean(x.reshape(-1,240)**2,axis=1))
        ax.plot((np.arange(len(rms))+.5)*.005,rms,label='V4 event' if label=='old' else 'V5 event',color=color)
    ax.axvline(.45,color='#555555',ls='--',label='Ignition OFF request')
    ax.axvline(1.,color='#555555',ls=':',label='Driver reaches OFF')
    ax.set(xlabel='Generated time / s',ylabel='5 ms event RMS / FS',xlim=(0,4));ax.legend();ax.grid(alpha=.2)
    fig.savefig(a.output/'cancellation.png',dpi=150);plt.close(fig)
    shutil.copy2(new/'abort.vsltake.json',a.output/'abort.vsltake.json')
    buttons=''.join(f'<button data-src="{name}" data-group="{group}">{label}</button>' for name,group,label in (
        ('old-mix.wav','abort','旧V4 · 完整干声'),('new-mix.wav','abort','修复V5 · 完整干声'),
        ('old-events.wav','abort','旧V4 · 只听事件'),('new-events.wav','abort','修复V5 · 只听事件'),
        ('A-reference.wav','source','A 原素材 · 35–40.5秒启动上下文')))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>启动中断 · C交接核查</title><style>body{margin:0;background:#f2f4f7;color:#172338;font:16px/1.7 system-ui}main{max-width:880px;margin:auto;padding:24px}h1{font-size:28px}section{background:white;padding:22px;border-radius:12px;margin:22px 0}button{display:block;width:100%;font:inherit;text-align:left;padding:12px;border:1px solid #bbc6d6;background:#f2f4f7;color:#172338;border-radius:6px;margin:10px 0;cursor:pointer}button[aria-pressed=true]{background:#215fcd;color:white}audio,img{width:100%}a{color:#215fcd}p{overflow-wrap:anywhere}.note{color:#667387}</style>
<main><small>VEHICLE SOUND / 实际C生命周期核查</small><h1>启动取消后，声音应当结束。</h1>
<p>0秒启动，0.45秒关闭点火，1秒到达熄火状态。旧V4在衰减4×时仍有接火尾音持续到3.48秒；V5在停机入口用20ms淡出，尾音在0.47秒结束。持续DNA、低频和细节逐样本保留。</p>
<section><strong id="label"></strong><audio controls preload="metadata"></audio>'''+buttons+'''
<small>一个播放器，无自动播放。同组切换保留进度，换组从头。两版均为实际C、输出增益0.25，无房间、压缩或逐条响度补偿。</small></section>
<img src="cancellation.png" alt="两版实际C事件分轨的均方根包络：旧版在熄火后仍有尾音，新版在停机入口淡出">
<p>这是中断行为修复，没有重新设计启动音色。独立停机末响可以保留自己的尾音；熄火后主动点击单次试听也仍可完整播放。正常启动／驾驶由原V4做逐样本对照，新的音色验收仍需继续。</p>
<p>A原素材提供车内启动上下文：能看到启动操作与仪表建立，随后低频建立。它没有实测RPM／燃油数据，也没有分离起动机、燃烧和座舱贡献；不与本次中断控制轨迹对齐。</p>
<p><a href="abort.vsltake.json">V5可回放中断行程</a> · <a href="report.json">新旧C与来源记录</a></p>
<p class="note">V4原行程请配合V4版本；V5使用新的DLL身份，原二进制和音色库均保留。当前声源库仍只有未验收的启动／接火候选，未新增正式回火或停机音色。</p></main><script src="app.js"></script></html>'''
    (a.output/'index.html').write_text(page,encoding='utf-8')
    shutil.copy2(repo/'tools/exhaust_return_review_web_v1.js',a.output/'app.js')
    report=dict(schema='vsl.startup-abort-review/1',goal_complete=False,timbre_accepted=False,
        source=origin,old=reports['old'],new=reports['new'],
        reference_is_not_synchronized_to_generated_controls=True,
        files={p.name:sha(p) for p in a.output.glob('*.wav')})
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(__file__,a.output/'executed_build.py')
    print(json.dumps(dict(output=str(a.output),goal_complete=False)))


if __name__=='__main__':main()
