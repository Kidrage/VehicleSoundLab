"""Generate a local listening page and scientific plots; never autoplay audio."""
from pathlib import Path
import sys,json,csv,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from html import escape
out=ROOT/'renders/v0.2.0'
# Same RPM/load, both mono, settled central 3 s; keep original exports intact.
old=out/'v010_5000_loaded.wav';new=out/'v02_5000_loaded_mono.wav'
subprocess.run([str(ROOT/'build/baseline-v010/Release/vsl_render.exe'),str(old),'--rpm','5000','--load','.85','--seconds','6'],check=True,capture_output=True)
subprocess.run([str(ROOT/'build/Release/vsl_render.exe'),str(new),'--rpm','5000','--load','.85','--width','0','--seconds','6'],check=True,capture_output=True)
pair={key:sf.read(path,always_2d=True)[0][48000*2:48000*5] for key,path in [('v010',old),('v02',new)]}
for key,x in pair.items():pair[key]=x*10**(-23/20)/np.sqrt(np.mean(x*x))
gain=min(1,.85/max(abs(x).max() for x in pair.values()))
for key,x in pair.items():sf.write(out/f'audition_{key}_5000_mono_rms_matched.wav',x*gain,48000,subtype='PCM_24')
trace=list(csv.DictReader((out/'v10_drive_trace.csv').open()))
t=np.array([float(r['seconds']) for r in trace]);num=lambda k:np.array([float(r[k]) for r in trace])
fig,ax=plt.subplots(4,1,figsize=(12,8),sharex=True,constrained_layout=True)
ax[0].plot(t,num('rpm'));ax[0].set_ylabel('RPM')
ax[1].plot(t,num('speed_kph'));ax[1].set_ylabel('km/h')
ax[2].plot(t,num('throttle'),label='throttle');ax[2].plot(t,num('load'),label='signed load');ax[2].plot(t,num('brake'),label='brake');ax[2].legend(ncol=3);ax[2].set_ylabel('controls')
ax[3].step(t,num('gear'),where='post',label='gear');ax[3].plot(t,num('shift_gain'),label='combustion shift gain');ax[3].legend();ax[3].set(xlabel='Seconds since render start',ylabel='gear / gain')
for a in ax:a.grid(alpha=.2)
fig.suptitle('V0.2 deterministic pedal drive / engineering model, not measured vehicle telemetry')
fig.savefig(out/'drive_trace.png',dpi=140);plt.close(fig)
fig,ax=plt.subplots(figsize=(11,5),constrained_layout=True)
for name in ['v10_5000_light','v10_5000_loaded','v10_5000_overrun']:
    x,sr=sf.read(out/f'{name}.wav',always_2d=True);f,p=signal.welch(x[2*sr:5*sr],sr,nperseg=8192,axis=0)
    ax.semilogx(f,10*np.log10(p.mean(axis=1)+1e-20),label=name.replace('v10_5000_',''))
ax.set(xlim=(40,16000),ylim=(-145,-35),xlabel='Hz',ylabel='PSD dB/Hz',title='Same 5000 RPM target / load-dependent spectra / no loudness matching')
ax.grid(alpha=.2);ax.legend();fig.savefig(out/'same_rpm_load_spectra.png',dpi=140);plt.close(fig)
for name in ['ui_live_preview','ui_listening']:
    source=ROOT/'renders'/f'{name}.bmp'
    if source.exists():Image.open(source).save(out/f'{name}.png')
def player(title,path,note=''):
    return f'<article><h3>{escape(title)}</h3><audio controls preload="none" src="{escape(path)}"></audio><p>{escape(note)}</p></article>'
prefix='../renders/v0.2.0/'
cards=''.join(player(title,prefix+name+'.wav',note) for title,name,note in [
 ('完整踏板驾驶 · stereo','v10_drive_stereo','30 秒：启动、怠速、加速、换挡、收油和刹车；保留动态。'),
 ('车内视点预览','v10_drive_cabin','同一驾驶输入；几何与简化遮挡预览，尚非实测车厢。'),
 ('同转速 · 轻负载','v10_5000_light','5000 RPM，负载 0.12；保留渲染电平，未单独归一化。'),
 ('同转速 · 重负载','v10_5000_loaded','5000 RPM，负载 0.85；频谱与分层权重一起变化。'),
 ('同转速 · 倒拖','v10_5000_overrun','5000 RPM，负载 -0.4；没有先前重油门历史，因此不自动回火。')])
comparisons=''.join(player(title,prefix+name+'.wav',note) for title,name,note in [
 ('0.1.0 · 5000 RPM mono','audition_v010_5000_mono_rms_matched','旧版已冻结源码重新构建；负载 0.85，取稳定 3 秒。'),
 ('0.2.0 · 5000 RPM mono','audition_v02_5000_mono_rms_matched','同 RPM / 负载；两份稳定片段作非加权 RMS 对齐。'),
 ('0.2.0 驾驶 · mono','audition_drive_mono_rms_matched','与右侧同一驾驶输入；整段 RMS 对齐，仅作空间比较。'),
 ('0.2.0 驾驶 · stereo','audition_drive_stereo_rms_matched','相同声源和驾驶状态，经不同空间设置渲染。')])
references=''.join(player(title,'../references/clean/'+name+'.wav',note) for title,name,note in [
 ('A · 启动动作语境','A_start_context_v02','原视频 33–40 秒，驾驶位；具体接火时刻未标定。'),
 ('A · 尾排驻车','A_idle_context_v02','原视频 208–211 秒，缩窄范围以避开后续镜头切换。'),
 ('A · 尾排行驶','A_road_context_v02','原视频 316–319.5 秒；绝对 RPM、负载与挡位未核实。'),
 ('B · 车内动态','B_cabin_pull','原录音 218–230 秒，保留双声道；仅有本地音频。')])
hybrid=''.join(player(title,'../references/analysis/v02/hybrid/'+name+'.wav',note) for title,name,note in [
 ('B 原录音 · 对齐副本','B_reference_rms_matched','与下面两份采用同一 RMS 对齐方法；不是 LUFS。'),
 ('B · 64 条轨迹／声道','B_osc64_per_channel_rms_matched','同片段离线拟合；不是实时 C 引擎。'),
 ('B · OSC 与受约束残差','B_osc64_plus_residual_rms_matched','加入新生成的频段噪声；不能修复全部相位／瞬态误差，可能仍过填。')])
html=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vehicle Sound Lab · V0.2 试听</title><style>
body{{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;background:#141922;color:#e1eaf2;max-width:1080px;margin:40px auto;padding:0 24px}}h1{{font-size:30px}}h2{{margin-top:42px;font-size:22px}}h3{{font-size:17px;margin:0 0 14px}}p{{color:#aebdce}}a{{color:#7bd8c8}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}article{{background:#202a37;padding:22px;border-radius:10px}}article p{{font-size:14px;margin-bottom:0}}audio{{width:100%}}img{{width:100%;border-radius:8px;margin:16px 0}}.tag{{color:#7bd8c8;font-size:13px;letter-spacing:1px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}
</style><div class="tag">VEHICLE SOUND LAB / 0.2.0</div><h1>从音色试验进入可驾驶的声浪系统</h1>
<p>先听完整驾驶，再用本地工具的 Start、油门、刹车和挡位亲自控制。当前音色仍是工程模板，尚未完成兰博基尼标定。页面不会自动播放；开始一段时会暂停其他音频。</p>
<p><a href="V6方法论与V02实现.md">研究与实现说明</a> · <a href="../renders/v0.2.0/drive_trace.png">驾驶控制日志图</a> · <a href="../renders/v0.2.0/scene.json">7.1.4 与声源元数据</a></p>
<h2>当前驾驶模型</h2><div class="grid">{cards}</div>
<h2>版本与空间对照</h2><p>以下是明确作 RMS 对齐的试听副本，原始导出保留。版本比较取同转速、同负载、双 mono 的稳定片段；空间比较使用同一套驾驶输入。</p><div class="grid">{comparisons}</div>
<h2>经画面复核的素材语境</h2><p>A 和 B 分开建档；录音视点不能直接当作真实麦克风坐标。以下参考片段维持固定余量处理，没有按段响度匹配。</p><div class="grid">{references}</div>
<h2>离线重建：检查高频和双声道假设</h2><p>三份均来自 B 的同一片段。残差包含跟踪、相位、瞬态和噪声误差；本实验不代表任意转速下的合成能力，也没有把残差波形塞进实时核心。</p><div class="grid">{hybrid}</div>
<h2>控制与路由</h2><img src="../renders/v0.2.0/drive_trace.png" alt="30 second simulated driving trace"><img src="../renders/v0.2.0/same_rpm_load_spectra.png" alt="Spectra at same RPM and different loads">
<p>7.1.4 文件和十个独立 mono float32 声源位于 renders/v0.2.0；通道顺序与位置见 scene.json。当前应用监听 stereo，12 声道须用支持该布局的 DAW／播放器。多声道文件已经校验，尚未实机试听。</p>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{{if(a!==b)b.pause()}})));</script></html>'''
(ROOT/'research/V02试听.html').write_text(html,encoding='utf-8')
print('Created V02 listening page, settled version comparison and plots')
