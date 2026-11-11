"""Build a focused fuel-excitation audition and implementation record."""
from pathlib import Path
import json
from comparison_page import comparison_page
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'renders/v0.7.0'
r=json.loads((OUT/'verification.json').read_text())
m=json.loads((OUT/'excitation_measurements.json').read_text())
labels={'lift':'5000 RPM 收油／重新加负载 · 7.5 秒',
        'lift_pure':'同一收油过程 · Pure OSC',
        'downshift':'闭油门制动与降挡补油 · 18 秒',
        'neutral':'空挡补油与转速回落 · 8 秒',
        'drive':'完整运动自动挡 · 30 秒'}
cases={key:dict(label=label,takes={tag:'../renders/v0.7.0/'+r['cases'][key][tag]['audition']['file'] for tag in ['bypass','enabled']},
    gain_note=f"同组两个副本统一增益 {r['cases'][key]['enabled']['audition']['gain_db']:.2f} dB，保留新旧相对电平与段内动态；未分别做 RMS／LUFS 匹配。切换保留播放位置。") for key,label in labels.items()}
extra='''<p>先听第一项 3–4.8 秒的收油，再听降挡中的补油。新版减少燃烧激励后，泵气、机体和机械声继续运行；是否更像真实发动机，需要结合听感判断。</p>
<details><summary>查看声音变化与驾驶过程</summary><p class="quiet">以下来自实际 C 导出。干声诊断关闭 IR，隔离排气激励与其他声源；常规试听仍含原来的短 IR。图中的断油时序是工程控制策略，没有冒充实车 ECU 测量。</p><img src="../renders/v0.7.0/dry_lift_sources.png" alt="固定转速下燃烧和泵气激励的变化，以及实际排气声源电平"><img src="../renders/v0.7.0/downshift_fueling.png" alt="制动中内部补油恢复燃烧，驾驶员油门保持关闭"></details>
<details><summary>素材给出的线索与限制</summary><p class="quiet">A 驻车与尾排行驶、B 车内片段的频带衰减不同步。音高、管路、空间与录音处理都可能参与，单靠这些能量变化不能认定断油。B 仍只有音频。</p><img src="../references/analysis/overrun_v1/recording_decays.png" alt="三个参考片段的独立频带功率观测"><p class="quiet">未增加素材清洗，也未改变原始参考电平。</p></details>
<p class="quiet">Sound detail 新增 Overrun fuel cut 与 Motored exhaust。关闭前者可以恢复上一版动态声音；SCI-FI 模板默认保持连续激励。主界面维持原来的驾驶与声音控件。</p>'''
footer='''<p><a href="V07断油与泵气激励.md">实现与验证</a> · <a href="V06试听.html">V0.6 点火几何对照</a></p><p class="quiet">可操作程序：E:\\VehicleSoundLab\\Launch.cmd。反馈时可注明场景、秒数，以及收油是否空、补油是否突兀、机械声是否过于规则。</p>'''
page=comparison_page(title='V0.7 · 断油与泵气激励',version='0.7.0',headline='收油后，发动机仍在转',
    intro='<p>把“停止燃烧”与“停止转动”分开。新增断油／恢复供油控制，以及由曲轴驱动的低压泵气声；降挡补油会恢复燃烧激励。</p>',
    cases=cases,methods={'bypass':'原激励 · 断油旁路','enabled':'V0.7 · 断油与泵气'},extra=extra,footer=footer)
(ROOT/'research/V07试听.html').write_text(page,encoding='utf-8')
d=r['device']
note=f'''# V0.7 断油与泵气激励

版本 0.7.0，单独构建 `build-v07`；`Launch.cmd` 指向新版。V0.1～V0.6 保留冻结版本。整个驾驶声浪目标仍为 active，本轮没有完成主观自然度、实车标定或扬声器阵列验收。

## 为什么继续分离激励

V0.6 的收油已经有独立工况包络，但运行中的 `drive.combustion` 始终为 1，持续排气仍按燃烧生成。V0.7 将生命周期许可、燃烧供给、曲轴运动、换挡衰减和有限事件分开：持续燃烧可以停止，旋转机体、机械和气流不因断油一并清空。

## 与 V6 的关系

本轮经 GitHub HEAD 接口复查，上游仍为 V6 基线提交 `ac2b37d8639027d79934a2023cf8d1d37d3b2f96`，记录在 `research/upstream_head_v07.json`。重新读取并校验该固定提交的实际 V10 Gen codebox 与 `drive_model.js`。Gen 的 `run = slide(clamp(engine_running * combustion_gain * shift_cut, 0, 1), 420, 1650);` 将三个控制合成运行增益；两缸列、残差和模块分工仍是有用起点。检查的驾驶控制器没有 `fuel_cut`／`fuelCut` 标识。本轮的独立断油状态与无燃烧泵气是本地扩展，不能说成直接移植了 V6 的实车 ECU 模型。原行、快照哈希与边界在 `references/analysis/overrun_v1/results.json`。

## 参考观测

继续读取批准的 A/B float32 主文件，左右声道功率分别计算后平均，不折叠 B 波形。4096 帧 Hann 窗、240 帧 hop、PSD 积分给出六频带功率；85.33 ms 窗支撑不允许声称 5 ms 事件精度。

A 237.983→238.233 s 的最大 250 ms 中高频下降候选约 −12.26 dB；28–120／120–400 Hz 反而约 +4.07／+6.50 dB。A 318.703→318.953 s 的 3–8 kHz 下降约 −16.04 dB，120–400 Hz 上升约 +6.04 dB。B 218.348→218.598 s 的 400–1200 Hz 约 −10.71 dB，而 3–8 kHz 约 −0.33 dB。

这些是同片段探索性的频带变化，包含音高、视角、管路、路风噪和录音处理；不是分离出的物理声源，也不是确定的踏板／换挡／断油标签。新增 A 237.7／238.1／238.4 s 与 318.6／318.85／319.1 s 抽帧：前组可见驻车尾部外景，后组为行驶中的尾排近景。没有可读转速、踏板、挡位或喷油信号，也不能证明抽帧之间完全无剪辑。B 无已核查视频。本轮没有将候选时间拟合成 ECU 延时，没有新增清洗或归一化。

## 模块和策略

| 模块 | 职责 |
|---|---|
| `src/profiles/fueling.c/.h` | 独立的工程阈值、迟滞、延迟、恢复和泵气腔体设置 |
| `src/drive/fueling.c/.h`、`fuel_types.h` | OFF／FIRE／DELAY／CUT／RESUME；只决定供给命令，不修改曲轴或车辆轨迹 |
| `src/core/excitation.c`、`excitation_types.h` | 采样率下平滑燃烧门控；同一点火几何的带限泵气脉冲驱动有限记忆腔体 |
| `src/core/engine.c` | 排气低阶和高阶合成后经过激励处理；其余声源保持独立 |
| `src/io/drive_trace.c`、`render_session.c` | 记录供给命令、实际激励与状态边界；新增边界触发日志 |
| `src/app/tuning.c`、`preset.c` | 两项细节控制、预设保存与向旧预设提供默认值 |

工程默认：高于怠速 900 RPM、有效油门 ≤1.5%、负负载时开始资格计时；前进挡 140 ms、N 挡 220 ms。已经断油时，低于怠速 +450 RPM、有效油门 ≥3.5%、负载回升、内部补油或用户关闭功能会恢复供给。恢复有 60 ms 保持，避免阈值附近反复切换。V10 默认对应 1750／1300 RPM；这些数字未经 Lamborghini ECU 标定。

燃烧门控分别采用 12／9 ms 起落。三项零直流谐波组成平滑泵气脉冲，每项检查采样率上界；两缸列继续使用 54°／90° 几何与独立的 0.38 ms 工程传播延时。脉冲驱动 320 Hz、Q=1.8 的简化带通腔体，供给恢复后其储能自然衰减。它只是可替换的低压声学模型，不是从实测歧管或 IR 得出的传递函数。

驾驶员油门、内部补油与离合传递仍独立：补油会恢复燃烧声，却不能通过断开的离合提供车轮驱动力，也不能武装驾驶员松油回火。SCI-FI 模板保持连续激励；以发动机模板导入的自制 DNA 会服从该模板的供给策略，可以关闭断油。

## 实际验证

九项 CTest 通过，新增测试覆盖计时复位、转速迟滞、N 挡、低转恢复、微小补油、用户旁路、SCI-FI、实际声源、多采样率腔体稳定性，以及断油中熄火不重新引入燃烧激励。旧测试继续覆盖驾驶、状态层次、点火几何、时钟、换挡、空间与核心不变量。

五个动态场景关闭新功能时，与冻结 V0.6 WAV 逐字节一致；开启后，旧日志每一条共同时间点的原有字段仍逐值一致。五模板的稳定带载 WAV 也逐字节一致。试听页五组／十个 PCM24 副本使用每组共同的固定增益，保留新旧相对电平；没有分别做 RMS 或 LUFS 匹配。原始导出保留。

固定 5000 RPM 干声诊断中，3.8–4.5 s 的断油排气声源比旁路低 {m['motored_vs_fired_exhaust_cut_window_db']:.2f} dB，且有非零泵气声；另关闭 Motored exhaust 后该段排气降到浮点静音。机体、机械、进气、左右气流、事件、路与风八个干声源逐字节一致。常规路径的机体声源含排气驱动的 IR 返回，所以不会把它声称为所有布局／湿声条件下完全不受排气影响。

闭油门降挡日志有 {m['downshift']['blip_trace_rows']} 个补油采样行，均恢复供给、驾驶员踏板保持关闭；制动段车速单调下降，内部补油没有新增回火事件。已知稳定谐波 DNA 互换通过，仍不能证明完整 Serum 还原或发动机自然度。

原生细节控件实际点击／滑动与非默认 0／42% 预设往返通过；另操作主面板 OUTPUT 滑杆，检查两种操作都不改变其他参数。修复了旧界面每次操作都会重写全部滑杆、使 0.32 秒释放量化成 0.31968 秒等细小漂移的问题。静音设备测试平均 {d['render_ms_mean']:.4f} ms／512 帧、最大 {d['render_ms_max']:.4f} ms；墙钟 {d['wall_seconds']:.4f} s、设备 {d['device_seconds']:.4f} s，队列耗空 {d['queue_empty_observations']}。这是内部 DSP 与设备调度证据，没有麦克风／环回听音。十个独立 float32 声源与 7.1.4 speaker bed 继续输出。

## 待完成

仍需听音判断收油是否过空、补油是否突兀，以及机械层是否因固定频率正弦而过于规则。下一步包括受激机械模态、循环差异、RPM×负载谱形、真实管路／空间传递、动力学与更充分的视频状态证据。当前资料不足以唯一识别这些参数；本版不以新增断油就宣称完成真实发动机模拟。
'''
(ROOT/'research/V07断油与泵气激励.md').write_text(note,encoding='utf-8')
print('Written V07 comparison and implementation record.')
