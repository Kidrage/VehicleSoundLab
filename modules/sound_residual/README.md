# Sound Residual · OSC V1

独立 C11 残差声层：补充当前 DNA 谐波表示之外的平均频带能量和左右相关性。它不负责驾驶状态、低频轰鸣、物理声源分离或空间渲染，尚未接入原生驾驶窗口，音色待听评。

| 文件 | 职责 |
|---|---|
| `profile.h/c` | `VSL_SOUND_RESIDUAL 1` 解析、范围校验和失败时保留原模型；读取属于非实时阶段。 |
| `oscillator.h/c` | 每频带两组错开频率的正弦 OSC，分别表达共享与独立声道成分。种子决定初始频率／相位；运行时不播放录音。 |
| `voice.h/c` | `sr_voice_init/set/process`；独立实例时钟、18ms 音高／增益跟随，输出交错 stereo double。 |

当前模型有 8 个频带（1.2–8kHz），每带 32 个共享 OSC 和 32 个独立 OSC，共 512 个。若一侧无独立成分，相应振荡器仍维持时钟。零增益也不暂停声源；分块方式不改变结果。固定频率的密集叠加会产生拍频，尚未拟合真实录音的时间包络。

对频带功率 `P_L/P_R` 和复相关 `rho`，共享组的右声道系数为 `sqrt(P_R) * rho`，独立组为 `sqrt(P_R * (1-|rho|²))`；OSC 的 `sqrt(2/N)` 幅度因子保持预期功率。交叉谱约定为 `conj(L)*R`，虚部符号有独立已知信号验证。模型不是左右发动机缸列的解释。

```c
/* 非实时：解析并初始化；初始化复制参数，不借用 profile 存储。 */
SrProfile profile;
SrVoice voice;
sr_profile_read(stream, &profile);
sr_voice_init(&voice, &profile, seed, 1.0, 0.0);
/* 控制／渲染线程串行调用；外部宿主负责线程间快照。 */
sr_voice_set(&voice, 1.0, 0.5);
sr_voice_process(&voice, stereo, frames);
```

处理期无分配、文件 I/O、UI、驾驶／空间状态。当前限 48kHz、相对音高 0.9–1.1、增益 0–1；模型最高频率按 1.1× 预留带宽。接口不实施限幅，宿主须预留混音余量。离线 float 原始生成峰值可超过 1，试听副本统一乘 0.25。

构建／验证由 `handoff/CMakeLists.txt` 提供 `sound_residual`、`VslResidual_probe`、`VslResidual_checks`。拟合在 `tools/residual_osc_v1/`；完整方法和限制见[研究记录](../../research/谐波间残差OSC_V1.md)。
