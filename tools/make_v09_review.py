"""Make a restrained pressure-variation audition, with explicit model limits."""
import json
from comparison_page import comparison_page
from runtime_review import ROOT
OUT=ROOT/'renders/v0.9.0'
r=json.loads((OUT/'verification.json').read_text())
m=json.loads((OUT/'pressure_measurements.json').read_text())
labels={'mid':'完整混音 · 4000 RPM 带载','high':'完整混音 · 8000 RPM 带载','idle':'完整混音 · 怠速 850 RPM',
    'lift':'完整混音 · 固定 5000 RPM 收油／恢复','neutral':'完整混音 · 空挡补油','shifts':'完整混音 · 换挡与熄火',
    'downshift':'完整混音 · 制动降挡补油','drive':'完整混音 · 30 秒驾驶','stress':'强度检查 · 4000 RPM／100% 不规则度（非默认）'}
cases={}
for name,label in labels.items():
    takes=r['cases'][name]
    cases[name]=dict(label=label,takes={tag:'../renders/v0.9.0/'+takes[tag]['audition']['file'] for tag in ['bypass','varied']},
        gain_note=f'完整立体声混音；这一组共同固定增益 {takes["varied"]["audition"]["gain_db"]:+.2f} dB。'+('强度检查使用 100% 不规则度；默认是 35%。' if name=='stress' else '新旧两遍的驾驶输入、空间与其他声层相同。'))
for name,takes in r['isolated'].items():
    cases['banks_'+name]=dict(label='两排气源独奏 · '+labels[name].split(' · ')[1],
        takes={tag:'../renders/v0.9.0/'+takes[tag]['file'] for tag in ['bypass','varied']},
        gain_note=f'左／右排气声源分别放在 L／R，未加监听空间。这一组共同固定增益 {takes["varied"]["gain_db"]:+.2f} dB；不是耳朵位置的立体声，也不是参考录音重放。')
extra='''<p>先听 4000／8000 RPM，再比较收油与完整驾驶。新版使用默认 35% 不规则度；最后的 100% 场景用于检查变化过强时的听感。可以在程序 Sound detail 中关闭 Per-firing pressure variation 恢复 V0.8，或调 Cycle irregularity。</p>
<p class="quiet">当前只验证波形不再高度重复、主转速和操控不受影响；不能据此认定已更像兰博基尼。变化强度、主排气谱形与实车传递关系仍需审听和标定。</p>
<details><summary>查看实际导出的信号</summary><img src="../renders/v0.9.0/pressure_spectra.png" alt="相同转速下实际排气声源的谱线与旁带"><img src="../renders/v0.9.0/pressure_states.png" alt="两侧压力幅度与到达时间的稀疏日志采样"><p class="quiet">旁带与重复性只表明变化机制生效，不能换算成真实度。</p></details>
<details><summary>参考素材与左右关系</summary><p>A 车外片段的中高频电平变化高度同步，B 车内双耳片段较弱。录音 L／R 混合了多个声源和空间，不能直接对应两个发动机缸列。下列副本均已批准，沿用固定 −6.02 dB、28 Hz 高通和 5 ms 端点淡化，没有归一化或降噪。</p><p>A · 原片 313.5–319.5 s，车外行驶情境；没有精确转速／踏板遥测。</p><audio controls preload="metadata" data-reference src="../references/clean/A_tailpipe_road_pull.wav"></audio><p>B · 原片 218–230 s，车内双耳录音；本地尚无已核对视频。</p><audio controls preload="metadata" data-reference src="../references/clean/B_cabin_pull.wav"></audio><img src="../references/analysis/pressure_variation_v1/recorded_level_changes.png" alt="四段参考录音的左右频带电平局部变化"></details>'''
page=comparison_page(title='V0.9 · 逐次燃烧压力变化',version='0.9.0',headline='同一转速，让每次燃烧有细小变化',
    intro='<p>在主排气层试做受限的幅度与压力到达时间变化，减少固定波形的重复。曲轴、转速、驾驶状态与两排气源位置继续独立控制。</p>',
    cases=cases,methods={'bypass':'V0.8 · 原排气波形','varied':'V0.9 · 逐次压力变化'},extra=extra,
    footer='<p><a href="V09逐次燃烧压力.md">实现与验证</a> · <a href="V08试听.html">上一版机械声对照</a></p><p class="quiet">启动：E:\\VehicleSoundLab\\Launch.cmd。可记录场景／秒数，以及电子嗡鸣、砂感、尖锐声线和收油过渡的具体变化。</p>')
(ROOT/'research/V09试听.html').write_text(page,encoding='utf-8')
d=r['device'];mid=m['steady_bank_sources']['mid'];high=m['steady_bank_sources']['high']
note=f'''# V0.9 逐次燃烧压力变化

版本 0.9.0，构建在 `build-v09`，入口 `Launch.cmd`。V0.1～V0.8 保留冻结历史。上一个 goal turn 为 progress；本轮继续主排气信号机制，完整驾驶模拟和自然度目标仍为 active。

## 为什么处理主排气

V0.8 的机械层比排气低约 40–51 dB，继续堆叠机械细节难以解决主声线过于规则的问题。既有 DNA 重复固定 720° 波形，高阶使用同一个曲轴时钟；原有循环不规则度主要是两个周期正弦，左右增益恰好反向。它可以产生变化，却不等于每次燃烧有差异。

本版保留现有谱形与工况映射，试做受限的逐压力间隔幅度／到达时间变化。它是可关闭的工程假设，还不能宣称根除了电子感、完成了实车 COV 拟合或改善了主观真实度。

## V6 的借鉴与区别

本轮通过 GitHub HEAD 接口再次核对，上游仍为 `ac2b37d8639027d79934a2023cf8d1d37d3b2f96` 的 V6 基线；记录在 `research/upstream_head_v09.json`。保留快照并核验实际 Gen codebox 哈希。V6 以 `cycle_variation` 调制 `bank_fire`，左右 `cylinder_l/r` 使用不同周期率；原行保存在 `references/analysis/pressure_variation_v1/results.json`。

本地保留其“循环变化属于发动机发声模块”的思路，但不调制驾驶系统曲轴，也不另造左右转速。720° 几何与 0.38 ms 工程传播延时继续独立。模拟的是压力波形的小幅变化，不是 ECU 点火角抖动或实车配气正时。

## 模块和公式

| 文件 | 职责 |
|---|---|
| `src/profiles/combustion.c/.h` | V10 压力幅度、到达时间范围、事件记忆和开关时间；均为工程值 |
| `src/core/combustion.c` | 两缸列独立随机流、压力间隔采样、平滑窗、相位变化和频率余量 |
| `src/core/combustion_types.h` | 事件系数、两侧增益／相位、计数与独立随机状态 |
| `src/core/dna.c`、`high_orders.c` | 消费同一套压力相位与幅度，不各自产生不相关抖动 |
| `src/io/drive_trace.c` | 压力系数更新数、幅度与到达时间稀疏采样；不冒充喷油遥测 |
| `src/app/tuning.c`、`preset.c` | 一个可旁路选项，复用现有不规则度；旧预设保留原声 |

V10 每侧缸列的等间隔压力相位记为 φ，窗 `w = (1 + cos φ)/2`。在两个压力中心的中点更新受限随机系数，此时窗值和一阶导数均为零。系数用 0.25 事件记忆平滑，各侧使用独立固定种子流。幅度 `g = 1 + mix × irregularity × spread × coefficient × w`；时间变化转成低阶 720° 相位 `δ = -2π × cycle_hz × arrival_seconds × coefficient × w × mix × irregularity`，同一 δ 也供高阶 OSC 使用。正到达时间表示延迟，因此相位为负。

幅度 spread 从低载 0.18 过渡到带载 0.09；到达时间范围从低载 120 µs 过渡到带载 45 µs。默认不规则度 35%，理论最大时间变化不超过 ±42 µs，幅度不超过 ±6.3%，实际还受随机系数和窗限制。高负载会缩小变化范围。开关采用 25 ms 混合，并逐渐移除原来强制反向的周期 AM；不重置驾驶或其他声源随机序列。

压力相位使用固定的实际曲轴加局部变化。`1 + π × bank_hz × arrival_seconds × irregularity × mix` 给出保守的瞬时频率伸缩余量，低／高阶分别预留采样率边界。平滑随机事件仍可能有很弱的高阶旁带，这不是对任意 FM 严格无混叠的数学证明。

供给关闭时不再更新新的燃烧压力系数，原排气燃烧门控仍由 `excitation.c` 负责；泵气、转动机械声、驾驶状态和其他声源不继承压力相位。内部补油恢复供给后，压力变化继续。计数表示压力系数更新，含初始化约定，不能当成逐缸喷油／点火计数。

当前仅工厂 V10 启用此配置。其他四模板与导入 DNA 保持原有波形／时钟。严格 Pure OSC 关闭该随机压力变化，切换时平滑退出，稳定后继续保持与随机种子无关的原行为。普通引擎模式仍使用 OSC 生成主音，没有运行时参考录音重放。

## 参考观测

直接读取批准 A/B 的 float32 主文件，单独计算左右功率；没有新下载、清洗或增益变化。四段为 A 208–213 s、237–249 s、316–319.5 s 与 B 218–230 s。2048 帧 Hann／240 帧 hop，频带 1200–3000 和 3000–8000 Hz，减去居中 255 ms 电平均值查看局部变化。

A 三段的左右局部电平相关度约 0.925–1.000，B 约 0.212–0.248。A 不能用于指定两缸列互相独立到什么程度；录音两声道包含声源混合与视角，不等于两个物理排气源。不同视角也不能共用同一声场标定。42.67 ms 窗支撑和电平去趋势不能识别逐次燃烧到达时间；120／45 µs 参数没有由这些统计拟合。

## 实际导出和验证

11 项 CTest 通过。新测试检查逐侧事件率、幅度／时间边界、低阶和高阶实际 OSC 的压力相位／幅度一致、曲轴独立、断油不更新／补油恢复、窗边界连续性、低采样率余量、旁路、导入 DNA 和严格 OSC 政策。原核心测试继续检查随机种子、主机 block 切分、几何、驾驶、换挡和空间不变量。

八个默认场景关闭新模块后，与冻结 V0.8 WAV 逐字节一致，原日志共同字段也逐值一致。五模板旁路均复现旧版，其他四模板即使开关保持打开也与旧版一致。零不规则度、严格 Pure OSC 和以发动机模板播放导入 DNA 的导出亦复现原信号。九组分轨中，进气、机械、左右气流、事件、路噪和风噪七个独立声源逐字节一致；机体中的 DNA→IR 返回有意随主排气改变，不能将湿机体声称为完全独立。

实际两排气源在 2.0–3.8 s 的相邻 720° 周期差分：4000 RPM 原左侧 {mid['bypass']['adjacent_720_cycle_difference_to_signal_db'][0]:.2f} dB、新版 {mid['varied']['adjacent_720_cycle_difference_to_signal_db'][0]:.2f} dB；8000 RPM 原左侧 {high['bypass']['adjacent_720_cycle_difference_to_signal_db'][0]:.2f} dB、新版 {high['varied']['adjacent_720_cycle_difference_to_signal_db'][0]:.2f} dB，均相对本身信号功率。它证明重复性降低，不是失真评分或真实度百分比。两侧平均稳态功率变化分别 {mid['varied']['bank_mean_power_dbfs']-mid['bypass']['bank_mean_power_dbfs']:+.3f} 和 {high['varied']['bank_mean_power_dbfs']-high['bypass']['bank_mean_power_dbfs']:+.3f} dB；没有通过单独增益匹配掩盖版本变化。

实际收油 3.8–4.7 s 压力更新计数停止；降挡补油的 {m['downshift']['blip_rows']} 行日志均保持驾驶员踏板关闭、供给恢复，压力更新继续。十个原始声源在 stereo／7.1.4 导出中逐字节一致，仍是 speaker bed，非 Atmos 对象和实机阵列验收。

UI 实际点击新增勾选项、检查参数隔离和非默认预设往返。缺少新选项的 V0.8 预设关闭本模块，同时保留其机械模型选择；V0.7 缺少两个选项的预设也保持相应旧模型。静音设备平均 {d['render_ms_mean']:.4f} ms／512 帧、最大 {d['render_ms_max']:.4f} ms，墙钟 {d['wall_seconds']:.4f} s／设备 {d['device_seconds']:.4f} s，队列耗空 {d['queue_empty_observations']}。这不是听音或环回验证。

## 试听与下一步

试听页有九组混音（含一个明确标注的 100% 强度检查）和三组两排气源独奏，每组共用固定增益。独奏的 L／R 是两个声源，不是耳朵位置的立体声。原始 float32 源、原始导出、配置与旧版继续保留。

尚需主观判断是否减少电子嗡鸣、是否引入不需要的砂感，以及尖锐高转声线是否仍然成立。主导的 RPM×负载谱形、真实进排气传递、动力学、同步视频状态和实际空间标定均未完成。下一步应检查主谱形／声学与驾驶动态，避免继续只用增加随机性替代标定。
'''
(ROOT/'research/V09逐次燃烧压力.md').write_text(note,encoding='utf-8')
print('Written V09 audition and implementation record.')
