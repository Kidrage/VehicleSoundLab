"""Focused comparison and implementation notes; shared player stays reusable."""
from pathlib import Path
import json
from comparison_page import comparison_page
from runtime_review import ROOT
OUT=ROOT/'renders/v0.8.0'
r=json.loads((OUT/'verification.json').read_text())
m=json.loads((OUT/'mechanical_measurements.json').read_text())
labels={'idle':'完整混音 · 怠速 850 RPM','mid':'完整混音 · 4000 RPM 带载','high':'完整混音 · 8000 RPM 带载',
    'lift':'完整混音 · 固定 5000 RPM 收油／恢复','neutral':'完整混音 · 空挡补油',
    'shifts':'完整混音 · 换挡与熄火','downshift':'完整混音 · 制动降挡补油','drive':'完整混音 · 30 秒驾驶'}
cases={}
for name,takes in r['cases'].items():
    gain=takes['driven']['audition']['gain_db']
    cases[name]=dict(label=labels[name],takes={tag:'../renders/v0.8.0/'+takes[tag]['audition']['file'] for tag in ['legacy','driven']},
        gain_note=f'立体声完整混音；这一组共同固定增益 {gain:+.2f} dB。保留新旧相对电平和动态。')
for name,takes in r['isolated'].items():
    cases['mechanical_'+name]=dict(label='机械独奏 · '+labels[name].split(' · ')[1],
        takes={tag:'../renders/v0.8.0/'+takes[tag]['file'] for tag in ['legacy','driven']},
        gain_note=f'单个 mono 声源，未加空间处理。这一组共同放大 {takes["driven"]["gain_db"]:+.2f} dB 用于检查细节；不能按此音量判断其在混音中的占比。')
extra='''<p class="quiet">默认机械层比排气层低约 40–51 dB；完整混音的差别可能很小。机械独奏经过明确放大，方便检查发声方式。新版仍会因周期性冲击产生阶次结构；共振频率和衰减是工程初值，尚未通过实车标定或主观验收。</p>
<details><summary>观察实际声源与控制</summary><img src="../renders/v0.8.0/mechanical_spectra.png" alt="三种转速下新旧机械声源的实际频谱"><img src="../renders/v0.8.0/mechanical_states.png" alt="断油时转动冲击继续、燃烧冲击停止的控制日志"><p class="quiet">谱线和计数只验证发声机制，不表示真实度提升比例。</p></details>
<details><summary>批准素材的进一步观察</summary><p>四段混合录音中的 1760／3100 Hz 局部峰随时间和视角变化，不能据此识别机体模态。本版没有从录音反推缸体参数。</p><img src="../references/analysis/mechanical_texture_v1/recorded_texture.png" alt="固定绝对功率标尺的四段参考频谱"><p class="quiet">A 原片 270–277 秒的既有参考副本；这是混合录音，不能单独代表机械源。副本沿用固定 −6.02 dB、28 Hz 高通和 5 ms 端点淡化；无归一化或降噪。</p><audio controls preload="metadata" data-reference src="../references/clean/A_engine_bay_texture.wav"></audio></details>
<p class="quiet">程序 Sound detail 的 Driven mechanical resonators 可实时切回旧机械声；Mechanical detail 调节该层。主界面继续保留驾驶、DNA／BODY／NVH、声场和回放控件。</p>'''
page=comparison_page(title='V0.8 · 受激机械共振',version='0.8.0',headline='让机械声由转动与燃烧激发',
    intro='<p>沿用状态驱动的分层结构，把原先两个持续机械载波替换为“冲击 → 衰减共振”。转动冲击与燃烧冲击分别控制，停转后保留短暂余振。</p>',
    cases=cases,methods={'legacy':'旧机械载波 · V0.7','driven':'受激机械共振 · V0.8'},extra=extra,
    footer='<p><a href="V08受激机械共振.md">实现与验证</a> · <a href="V07试听.html">上一版断油对照</a></p><p class="quiet">启动：E:\\VehicleSoundLab\\Launch.cmd。可按“场景／秒数／具体听感”记录反馈；整套实车自然度与驾驶模拟目标仍在进行。</p>')
(ROOT/'research/V08试听.html').write_text(page,encoding='utf-8')
d=r['device']
note=f'''# V0.8 受激机械共振

版本 0.8.0，构建在 `build-v08`，主入口 `Launch.cmd`。V0.1～V0.7 保留冻结历史。本轮是可撤回、可单独审听的机械声机制扩展，没有达到整套系统的实车自然度验收。

## 状态方法论与本地扩展

继续使用固定的上游 V6 快照 `ac2b37d8639027d79934a2023cf8d1d37d3b2f96`：驾驶控制、生命周期、运行工况、独立连续层、瞬态事件与空间分开维护。V0.7 已扩展供给状态，本轮扩展受激机械声；不能把这些本地模型称为上游实测 Lamborghini 模型。运动自动挡仍在松油时保挡，在制动和转速安全条件下降挡。

原机械层在 1760 与 3100 Hz 持续产生两个载波，再以曲轴节奏调制幅度。即使包络分层，固定载波本身仍缺少“施力—结构储能—衰减”关系。本版提供显式旧模型旁路，便于隔离判断。

## 模块与参数

| 文件 | 职责 |
|---|---|
| `src/core/modal.c/.h` | 通用阻尼正弦状态；按秒定义极点衰减，接收采样间发生的冲击 |
| `src/profiles/mechanical.c/.h` | 五个模态及冲击权重、偏移角和总体量；共享工程数据，可另行替换 |
| `src/core/mechanical_modal.c` | 720° 曲轴事件、独立转动／燃烧随机流、冲击计数、储能与模型切换 |
| `src/core/mechanical.c` | 机械声源接口、旧载波旁路与原进气层 |
| `src/core/orchestrator.c` | 独立转动包络；起动时允许有转动声，供给关闭不等于曲轴停止 |
| `src/app/tuning.c`、`preset.c` | 细节勾选项与预设往返；主界面布局保持简洁 |
| `src/io/drive_trace.c` | 转动包络、模型混合量、两种冲击计数及储能 |

模态初值为 610／1180／2240／3870／5820 Hz，幅度衰减常数 20／13／9／6／4 ms，总体量 0.10。理想化转动冲击相对点火角偏移 360°／540°；不是实测配气正时。模态是工程共振数据，不是从混合录音识别的机体 FRF。每缸每 720° 有一个燃烧结构冲击与两个转动冲击，共享已有 54°／90° 点火事件表。

燃烧冲击使用机械工况包络 × 燃烧压力门控；转动冲击使用独立转动包络。断油只减少燃烧激励，起动机旋转和倒拖仍能施加机械冲击。两类冲击使用独立的固定种子随机流，只作受限幅度变化，不重定音高，也不影响气流、事件或 DNA 随机状态。共振在零转速时继续衰减，停止施力后不会立刻清零。模型开关采用 20 ms 交叉淡化；SCI-FI 不产生本层激励。

## 素材观测与边界

新增 `references/analysis/mechanical_texture_v1`，直接读取批准的 float32 主文件：A 尾排怠速 208–213 s、A 机舱情境 270–277 s、A 驻车补油 237–249 s、B 车内 218–230 s。使用 4096 帧 Hann 窗／240 帧 hop，分别计算左右功率后平均，频谱图固定同一绝对 PSD 标尺。没有重新清洗、修改主文件或折叠双耳波形。

对旧载波频率作探索性局部峰检查：1760 Hz 高于邻域中值 6 dB 的窗占比在四段中约 18–37%，3100 Hz 约 12–24%。它们不是稳定独占的机械标记；阶次经过、进排气、麦克风、反射与录音处理均可能造成局部峰。这项观察不能确定新的五个模态，更不能把能量覆盖当真实度。B 本轮仍没有视频遥测。

## 实际导出验证

十项 CTest 通过，新增解析衰减／频率、采样间冲击时刻、各采样率稳定性、每缸事件数、停转余振、断油转动冲击、起动转动包络和开关淡化。原有驾驶、声音状态、点火几何、独立 DNA 时钟、换挡、供给和空间测试继续通过。

八个场景关闭新机械模型后，与冻结 V0.7 WAV 逐字节一致，所有共同时间点的原有驾驶日志字段逐值一致。五种模板的旧模型旁路及 Pure OSC 收油导出亦复现旧版。七组有完整分轨的场景中，其余九个 float32 声源逐字节一致。十个声源在 stereo 和 7.1.4 导出中逐字节一致，7.1.4 仍是 mask `0x2d63f` 的 speaker bed，没有 Atmos 对象封装或实机阵列验收。

实际固定 5000 RPM 收油日志显示，3.8–4.7 s 燃烧冲击计数保持不变，转动冲击继续增长；3.8–4.5 s 机械声源 RMS 为 {m['cut_window']['mechanical_rms_dbfs']:.2f} dBFS。降挡日志有 {m['downshift']['blip_rows']} 行内部补油采样，踏板关闭、供给恢复，后续燃烧冲击恢复。熄火到 OFF 后不再施加冲击，已存储能量单调衰减到浮点静音。

原生 UI 实际操作新勾选项，验证仅修改该参数；非默认预设往返通过。旧预设如果缺少机械模型选项，会保留旧机械声；该兼容路径也在实际程序中通过。上一版供给／泵气控件与主面板 OUTPUT 的隔离检查继续通过。静音设备测试平均 {d['render_ms_mean']:.4f} ms／512 帧、最大 {d['render_ms_max']:.4f} ms；墙钟 {d['wall_seconds']:.4f} s／设备 {d['device_seconds']:.4f} s，队列耗空 {d['queue_empty_observations']}。这不是环回听音结果。

## 怎样审听本版

试听页有八组立体声混音和五组机械 mono 独奏，每组的新旧副本使用同一固定增益。机械独奏明确放大，不按该响度代表最终混音。实际稳态机械源比两排气声源的平均功率低约 40–51 dB，完整混音的变化可能很小；不能靠增加此层就解决高转音色失真或自然度不足。

下一轮重点仍是主导的排气／DNA 在 RPM×负载下的谱形、循环变化和传递关系，而不是无限叠加细节层。仍需同步视频状态证据、动力学、进排气／车身／空间标定及实际听音。当前五个模态、理想正时和共享工况数据均等待校准。
'''
(ROOT/'research/V08受激机械共振.md').write_text(note,encoding='utf-8')
print('Written V08 comparison page and implementation record.')
