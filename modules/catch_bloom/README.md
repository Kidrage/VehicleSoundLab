# 接火相干低频附加层

48kHz、C11。输入是持续DNA的左右声道，输出只有新增低频，不含原DNA。固定带通保留输入的谐波节奏；不产生独立噪声、燃烧脉冲或素材循环。

| 文件 | 职责 |
|---|---|
| `profile.*` | 1–4个固定模式、共同beta形状与起落时间；非实时事务读取／校验 |
| `filter.*` | 左右独立状态、相同系数的RBJ单位峰值带通；固定稳定极点 |
| `envelope.*` | 归一化beta凸起、指数跟随 |
| `voice.*` | 拥有模型与滤波状态，独立量18ms跟随；持续处理并输出附加量 |

`cb_voice_init`在非音频阶段拥有模型副本。宿主用**同一驾驶器**的CATCH状态和归一化生命周期进度调用`cb_voice_set`，然后`cb_voice_process`处理交错L/R；允许输入输出同址。关闭／量0仍推进滤波状态，不重置源相位。处理无分配、文件、设备、空间或车辆积分。

```text
delta[c] = amount × smooth(beta(progress)) × Σ gain[i] × bandpass[i](DNA[c])
```

当前可由`atlas_drive`通过`AdConfig.catch_profile`＋`AdMix.catch_gain`可选调用；正量要求有效模型。输入为互补低频重分配之前的完整包络后DNA，输出经同一主增益只加一次FL/FR；独立分轨为`AdCapture.catch_bloom`。`Launch-Catch-Study.cmd`提供原生研究入口，接火量默认0%；schema5行程拥有模型并记录第27字段。模型是A车内混合录音的粗颜色／包络，不能称独立车体传递、真实RPM或完整接火恢复。见[原始测量](../../research/接火低频建立V1.md)及[集成与验证](../../research/接火低频统一驾驶V1.md)。
