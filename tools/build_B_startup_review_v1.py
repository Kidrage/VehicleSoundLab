"""Readable source/envelope review; reuse the single-player audio transport."""
import argparse
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];report=load(a.candidate/'report.json')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    source=Path('E:/VehicleSoundLab/references/analysis/B_startup_context_v1/crank-author1/reference.wav')
    x,rate=sf.read(source,always_2d=True);assert rate==48000
    sf.write(a.output/'reference.wav',np.pad(x*.25,((0,9600),(0,0))),rate,subtype='FLOAT')
    tracks=[dict(file='reference.wav',group='texture',label='原录音 · 启动早期选区',duration=.95),
        dict(file='held.wav',group='texture',label='持续门控候选 · 实际 C',duration=.95),
        dict(file='decay.wav',group='texture',label='初次衰减版本 · 保留对照',duration=.95),
        dict(file='context.wav',group='context',label='原录音上下文 · 12–20秒',duration=8.)]
    for src,dest in [('crank-hold-author1-monitor.wav','held.wav'),('crank-author1-monitor.wav','decay.wav'),
        ('B_12_to_20_monitor.wav','context.wav')]:shutil.copy2(a.candidate/src,a.output/dest)
    shutil.copytree(a.candidate/'editable-crank',a.output/'parameters')
    shutil.copy2(repo/'tools/exhaust_return_review_web_v1.js',a.output/'app.js')
    fig,axes=plt.subplots(2,1,figsize=(10,6),layout='constrained')
    for label,wave in [('Original early texture',x),('Held C candidate',sf.read(a.output/'held.wav',always_2d=True)[0][:36000]/.25),
        ('Initial decaying C',sf.read(a.output/'decay.wav',always_2d=True)[0][:36000]/.25)]:
        energy=np.mean(wave*wave,axis=1);rms=np.sqrt(energy.reshape(-1,240).mean(axis=1))
        axes[0].plot((np.arange(len(rms))+.5)*.005,rms,label=label)
        cumulative=np.cumsum(energy);axes[1].plot(np.arange(len(energy))/48000,cumulative/cumulative[-1],label=label)
    axes[0].set(ylabel='5 ms RMS / FS',title='Same B early-start interval: mean spectrum alone misses time structure')
    axes[1].set(xlabel='Time within the fixed 0.75 s crop / s',ylabel='Cumulative energy fraction',ylim=(0,1.02))
    for ax in axes:ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.savefig(a.output/'envelope.png',dpi=140);plt.close(fig)
    buttons=''.join(f'<button data-src="{v["file"]}" data-group="{v["group"]}">{v["label"]}</button>' for v in tracks)
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>B 启动早期纹理 · 包络核查</title><style>body{margin:0;background:#f2f4f7;color:#172338;font:16px/1.7 system-ui}main{max-width:860px;margin:auto;padding:24px}h1{font-size:28px;line-height:1.3}section{background:white;padding:22px;border-radius:12px;margin:20px 0}button{display:block;width:100%;font:inherit;text-align:left;margin:10px 0;padding:12px;border:1px solid #bbc6d6;border-radius:6px;background:#f2f4f7;color:#172338;cursor:pointer}button[aria-pressed=true]{background:#215fcd;color:white}audio,img{width:100%}a{color:#215fcd}p,small{overflow-wrap:anywhere}.transport{position:sticky;top:0;z-index:1;box-shadow:0 2px 12px #17233818}</style>
<main><small>VEHICLE SOUND / STARTUP TEXTURE</small><h1>启动纹理：保住持续感</h1>
<p>本轮只检查 Tecnica 车内录音的启动早期短段。初次模型衰减过快，持续候选使用同一选区重新提取，并保持到释放。它尚未通过音色听评。</p>
<section class="transport"><strong id="label"></strong><audio controls preload="metadata"></audio><small>一个播放器，无自动播放。所有音频固定增益0.25，没有分别归一化、限幅或新增房间效果。</small></section>
<section><h2>对照试听</h2>'''+buttons+'''<p>短段为原素材15.20–15.95秒。原声尾部补0.20秒静音，便于与合成对照。上下文可听到后续启动声建立；该部分没有在这条早期候选中合成。</p>
<p>先比较持续感，再判断是否像机械声。此候选没有还原原录音的转速轨迹，也没有将启动机与燃烧声物理分离。</p></section>
<section><h2>为什么保留这个候选</h2><img src="envelope.png" alt="原声、持续候选与初次衰减模型的能量包络对照">
<p>初次模型虽然平均频谱接近，但能量过早结束。持续候选改善了时间分布；它仍缺少原声的部分局部起伏，不能仅凭频谱和包络数字判定音色完成。</p></section>
<section><h2>在工作台继续编辑</h2><p>“独立事件”页选择 <strong>B Tecnica · 启动早期持续纹理候选</strong>。可调整模态、纹理与包络，保存版本并导出。声音由 C 生成，参数包不包含运行时录音。</p>
<p><a href="parameters/parameters.json" download>可编辑参数 JSON</a> · <a href="parameters/parameters.csv" download>参数表 CSV</a> · <a href="parameters/profile.h" download>C 参数头</a> · <a href="parameters/event-design.zip" download>完整参数包</a> · <a href="report.json">来源记录</a></p>
<p>启动建立段相对后续运转声的全频对比约2.09 dB，低于工具现有3 dB门槛，已保留为诊断工程，未生成接火参数。本页不更改正式音色或车辆配方。</p></section></main><script src="app.js"></script></html>'''
    (a.output/'index.html').write_text(html,encoding='utf-8')
    save(a.output/'report.json',dict(schema='vsl.B-startup-texture-review/1',tracks=tracks,
        project_id=report['editable_project_id'],source_seconds=[15.2,15.95],source_context_seconds=[12,20],
        mono_C_candidate_and_native_stereo_reference=True,monitor_gain=.25,padded_reference_tail_seconds=.2,
        no_autoplay=True,timbre_accepted=False,global_bank_changed=False,spatial_processing=False,
        files={v.name:sha(v) for v in a.output.iterdir() if v.is_file()}))
    print(a.output,flush=True)


if __name__=='__main__':main()
