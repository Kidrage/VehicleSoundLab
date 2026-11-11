"""Create a review page and a plot from the actual V0.5 driving trace."""
from pathlib import Path
import csv
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'renders/v0.5.0'
sys.path.insert(0,str(ROOT/'tools/python_deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

r=json.loads((OUT/'verification.json').read_text())
labels={'drive':'完整运动自动挡 · 30 秒','shifts':'手动换挡与停机 · 13 秒','neutral':'驻车空挡补油 · 8 秒',
        'lift':'固定转速收油 · 7.5 秒','steady5000':'5000 RPM 工厂音色 · 6 秒','custom_dna':'导入 110 Hz DNA 混合 · 6 秒',
        'downshift':'闭油门连续制动降挡 · 18 秒（仅 V0.5）'}
data={key:dict(label=labels[key],takes={v:'../renders/v0.5.0/'+case[v]['audition']['file'] for v in ['v04','v05']},
               gains={v:case[v]['audition']['gain_db'] for v in ['v04','v05']}) for key,case in r['cases'].items()}
data['downshift']=dict(label=labels['downshift'],takes={'v05':'../renders/v0.5.0/'+r['downshift']['audition']['file']},
                       gains={'v05':r['downshift']['audition']['gain_db']})
with (OUT/'downshift_v05.csv').open() as f:rows=list(csv.DictReader(f))
start=next(float(x['seconds']) for x in rows if float(x['blip'])>0)
window=[x for x in rows if start-.18<=float(x['seconds'])<=start+.52]
t=np.array([float(x['seconds']) for x in window])
fig,axes=plt.subplots(3,1,figsize=(10,7),sharex=True,layout='constrained')
for key,label in [('rpm','Engine RPM'),('shift_target_rpm','Shift target RPM')]:
    values=[float(x[key]) if key=='rpm' or x['shift_stage']!='NONE' else np.nan for x in window]
    axes[0].plot(t,values,label=label)
axes[0].set_ylabel('RPM');axes[0].legend(loc='best',ncol=2)
for key,label in [('throttle','Driver pedal'),('engine_throttle','Engine throttle'),('clutch_transfer','Clutch transfer')]:
    axes[1].plot(t,[float(x[key]) for x in window],label=label,
                 linestyle=':' if key=='throttle' else '-',zorder=3 if key=='throttle' else 2)
axes[1].set_ylabel('Command / fraction');axes[1].legend(loc='best',ncol=3)
for key,label in [('exhaust_gain','Exhaust'),('body_gain','Body'),('intake_gain','Intake'),('high_gain','High orders')]:
    axes[2].plot(t,[float(x[key]) for x in window],label=label)
axes[2].set_ylabel('Control envelope');axes[2].legend(loc='best',ncol=4);axes[2].set_xlabel('File time (seconds)')
for a in axes:a.grid(alpha=.22)
fig.suptitle('V0.5 engineering model: closed-pedal 4 -> 3, not measured car telemetry')
fig.savefig(OUT/'downshift_trace.png',dpi=160);plt.close(fig)

options=''.join(f'<option value="{key}">{label}</option>' for key,label in labels.items())
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V0.5 · 降挡衔接与独立 DNA 时钟</title><style>
*{box-sizing:border-box}body{margin:0;background:#111a22;color:#dfeaf0;font:16px/1.7 system-ui,sans-serif}main{max-width:900px;margin:40px auto;padding:0 24px 60px}
h1{font-size:29px;line-height:1.4;margin:8px 0 20px}.tag{color:#88d8c0;font-size:13px;letter-spacing:1px}h2{font-size:19px;margin:0 0 14px}
section{margin:24px 0;padding:26px;border:1px solid #31434f;border-radius:14px;background:#192733}.quiet{font-size:14px;color:#a0b6c2}
select{width:100%;font:inherit;color:#e3eff3;background:#111d27;border:1px solid #4b6574;border-radius:7px;padding:11px}label{font-size:14px;display:block;margin-bottom:8px;color:#bed0d9}
.buttons{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0}button{font:inherit;padding:12px;background:#233745;color:#deebee;border:1px solid #496674;border-radius:8px;cursor:pointer}
button[aria-pressed=true]{background:#a7e7d2;color:#092b24;border-color:#a7e7d2}button:disabled{opacity:.35;cursor:default}button:focus-visible,select:focus-visible{outline:3px solid #a7e7d2;outline-offset:3px}
#now{color:#a7e7d2;min-height:28px}audio{display:block;width:100%;margin:16px 0}p{margin:10px 0}a{color:#8ad9c5}img{width:100%;border-radius:8px}details{margin:22px 0}summary{cursor:pointer;color:#b0cbd8}
@media(max-width:550px){main{padding:0 16px 40px;margin-top:26px}section{padding:18px}h1{font-size:25px}}
</style><main><div class="tag">VEHICLE SOUND LAB · 0.5.0</div><h1>降挡先匹配转速，再接回车轮</h1>
<p>运动自动挡继续松油保挡、制动安全降挡。本版将断开、转速匹配、接合拆开控制；补油短暂打开进气与排气，机体和机械层保留各自的响应。</p>
<section><h2>试听</h2><label for="case">场景</label><select id="case">OPTIONS</select>
<div class="buttons" role="group" aria-label="版本"><button data-method="v04" aria-pressed="false">V0.4 · 冻结参考</button><button data-method="v05" aria-pressed="true">V0.5 · 当前版本</button></div>
<div id="now" role="status" aria-live="polite"></div><audio id="player" controls preload="metadata"></audio><p id="gain" class="quiet"></p>
<p class="quiet">切换保留文件时间。车辆使用相同宿主输入，但新的离合与扭矩传递会改变车速和换挡时刻，事件不逐点对齐。试听副本明示整段 stereo 非加权 RMS 增益，保留段内动态。</p></section>
<p>建议先听“闭油门连续制动降挡”的 11.5、13、15 秒附近，再比较完整自动驾驶的制动段。“5000 RPM 工厂音色”两版文件完全相同，便于确认持续音色没有随本次换挡修改而漂移。</p>
<p>“导入 110 Hz DNA”使用已知谐波工程测试音。新版给 DNA 独立变调时钟，气流脉冲仍跟随发动机转速，并恢复可单独调节的机械／进气层。它用于核查分层结构，尚未模拟用户的 Serum 音色。</p>
<details><summary>查看一次实际降挡的控制日志</summary><p class="quiet">曲线来自本地合成器，不是实车测量；包络为控制量，不能当作分层响度。补油时驾驶员油门为零，离合传递为零。</p><img src="../renders/v0.5.0/downshift_trace.png" alt="V0.5 闭油门降挡的转速、踏板、离合和各层控制包络"></details>
<p class="quiet">时序、转速执行器、频谱、机械与空间参数仍是工程值。数值正确不等于已经达到 Lamborghini 的自然度。听感、RPM／负载标定、物理 NVH 与真实声学继续推进。</p>
<p><a href="V05降挡与独立时钟.md">实现与验证记录</a> · <a href="V04试听.html">V0.4 高频对照</a> · <a href="立体声OSC试听.html">离线立体声研究</a></p>
<p class="quiet">可操作程序：E:\\VehicleSoundLab\\Launch.cmd。反馈可注明版本、场景和秒数，尤其是补油是否太短、太亮，以及收油到再开口的衔接是否自然。</p>
</main><script>
const data=DATA,names={v04:'V0.4',v05:'V0.5'};
const audio=document.getElementById('player'),selector=document.getElementById('case'),status=document.getElementById('now');let method='v05',serial=0;
function load(preserve){if(!data[selector.value].takes[method])method='v05';const token=++serial,position=preserve?audio.currentTime:0,playing=preserve&&!audio.paused;audio.pause();audio.src=data[selector.value].takes[method];status.textContent=data[selector.value].label+' · '+names[method];
document.getElementById('gain').textContent='本试听副本增益 '+data[selector.value].gains[method].toFixed(2)+' dB；整段 RMS 对齐至 −23 dBFS，按组共同留峰值余量；未做 LUFS 匹配。';
audio.onloadedmetadata=()=>{if(token!==serial)return;audio.currentTime=Math.min(position,Math.max(0,audio.duration-.02));if(playing)audio.play().catch(()=>{});};
for(const b of document.querySelectorAll('[data-method]')){b.disabled=!data[selector.value].takes[b.dataset.method];b.setAttribute('aria-pressed',b.dataset.method===method?'true':'false');}audio.load();}
selector.addEventListener('change',()=>load(false));for(const b of document.querySelectorAll('[data-method]'))b.addEventListener('click',()=>{method=b.dataset.method;load(true);});load(false);
</script></html>'''.replace('OPTIONS',options).replace('DATA',json.dumps(data,ensure_ascii=False))
(ROOT/'research/V05试听.html').write_text(page,encoding='utf-8')

d=r['device'];s=r['downshift']['trace']
note=f'''# V0.5 降挡与独立时钟

当前运行核心 0.5.0，独立构建 `build-v05`，入口 `Launch.cmd`。0.1～0.4 的冻结目录保留。本版不是持续工厂音色重调；五模板各在 4000 RPM、0.65 负载、三秒导出，新旧 WAV 逐字节一致，5000 RPM 的额外对照也一致。

## V6 的继承与本地扩展

继续采用已核查 V6 提交 `ac2b37d8639027d79934a2023cf8d1d37d3b2f96` 的固定控制时钟、生命周期、踏板到车辆状态、状态到分层包络和条件事件。上游 `research/upstream_v6/code/drive_model.js` 的 beginShift/updateShift（约 283～330 行）提供方向、cut/sweep/engage 和固定时长转速插值；本版受误差约束的匹配与独立补油是本地扩展，不声称来自 V6 的实测补油模型。上游 V10 也不是 Lamborghini 标定。

## 时钟分离

`src/core/clocks.c` 始终按 RPM/120 推进 720° 发动机周期；NVH 脉冲、机械调制与循环变化都使用它。导入 DNA 单独按根音 × RPM/3000 推进 pitch_phase。PAD 原本已有自己的 RPM 时钟，本次没有把它算作旧耦合问题。

`dna.c` 消费正确时钟；`mechanical.c` 取消因导入 DNA 而完全跳过的行为。导入后，工厂高阶谐波继续旁路，机械与进气由独立旋钮控制。Pure OSC 仍旁路所有非振荡器声音。空间 IR 消费排气信号，因此会有预期的 DNA 依赖；时钟测试在 SPACE/IR=0 时比较活跃的非排气声源。

## 换挡模块

- `src/drive/shift.c/.h`：断开、匹配、接合及失败处理；驾驶主控制器维护踏板和车辆积分。
- `src/profiles/transmission.c/.h`：断开 40 ms，最短匹配升挡 90 ms／降挡 140 ms，接合 100 ms，匹配响应 35 ms；上升最多 28000 RPM/s，下降 36000 RPM/s。误差不超过 80 RPM 才开始接合；接合误差过大重新匹配，超时或目标超转时退入 N。全部是工程参数。
- `powertrain.c`：离合传递同时作用于车轮驱动力和发动机制动。车轮推力只用驾驶员踏板；内部补油不能透过断开的离合驱动车轮。当前仍是简化纵向模型和受控 RPM 跟随器，没有曲轴惯量、摩擦扭矩与双离合动力学求解。
- `core/orchestrator.c`、`profiles/voicing.c`：新增 REV MATCH 工况与逐层切断释放比例；补油暂时恢复排气、进气和高阶细节，机体／机械继续保留慢响应。有效发动机油门及其变化率进入声音控制；驾驶员踏板及其变化率独立保留，用于松油回火资格。
- `core/events.c`：换挡击发仅允许正负载前进挡升挡；降挡、进出空挡不因同一个 shift 计数而伪造回火。正常大油门收油仍可能触发自己的有限回火。
- `drive/scenarios.c`：新增 downshift 宿主输入脚本，闭油门制动时连续 4→3→2→1；没有直接设置积分车速或 RPM。
- `io/drive_trace.c`：记录驾驶员／发动机油门、blip、离合、阶段、目标 RPM、误差和中止数；换挡期间密集记录。

## 验证与实际导出

七项 CTest 通过，JUnit 在 `renders/v0.5.0/ctest.xml`。新增测试验证实际振荡输出的 3000／6000 RPM 根音关系，以及不同 DNA 根音下活跃机械、气流等非排气声源的样本一致性；驾驶测试逐控制步核对闭油门补油、无意外加速、接合误差、升挡无补油、N 和超转保护、补油不能武装松油回火、熄火清除。

闭油门降挡实际导出：记录到 {s['recorded_blip_frames']} 个带补油的帧，驾驶员油门均低于 0.001；六次接合，开始接合时最大转速误差 {s['max_engage_error_rpm']:.3f} RPM，中止数零。三次升挡加三次降挡构成完整脚本；九秒半的大油门收油有一次独立回火事件，不把它归因为后续补油。

六组 V0.4／V0.5 对照加一组 V0.5 降挡，共 13 个 PCM24 试听副本，增益均记录。新的离合扭矩会改变驾驶轨迹，不能声称新旧 CSV 相同或切换时事件严格同步。独立对象 float32 声源与 7.1.4 bed 已导出；对象坐标、通道掩码与 stereo／12ch 声源不变性继续校验，尚未在物理阵列试听。

已知稳定谐波 WAV→DNA→当前 C runtime 的互换通过（残差 −84.63 dB，主峰约 219.33 Hz）。它仅验证互换，不证明能还原 Serum 的动态、Unison 或复杂 FM。

设备 smoke：平均合成 {d['render_ms_mean']:.4f} ms／512 帧，最大 {d['render_ms_max']:.4f} ms；墙钟 {d['wall_seconds']:.4f} s、设备 {d['device_seconds']:.4f} s，队列耗空 {d['queue_empty_observations']}。设备提交静音而内部执行完整 DSP，未做环回或扬声器听音。

## 待继续

自然度和声音开合需试听确认；现有素材没有精确踏板、扭矩、挡位和 RPM 遥测，本轮没有新增实车时序证据。下一步仍需按已有视频证据与音频推断分开标记，校准 RPM×负载谱形、燃油切断／残余激励，替换固定机械近似并拟合独立声学。当前声浪与完整驾驶目标仍为 active。
'''
(ROOT/'research/V05降挡与独立时钟.md').write_text(note,encoding='utf-8')
print('Written V05 review, trace plot and implementation record.')
