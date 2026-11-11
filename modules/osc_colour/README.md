# OSC 声线轴（独立诊断）

此模块只编译和跟随谐波幅度形状。它不判断换挡、负载、喷油或驾驶状态；不生成第二套时钟、相位或随机流，也不读取 PCM。

| 文件 | 职责 |
|---|---|
| `profile.h/c` | 非实时、事务读取 `VSL_OSC_COLOUR 1`；2–16 个严格递增阶次结点，阶次大于0且不超过320、增益±24 dB；按 log 阶次插值并编译线性幅度数组 |
| `envelope.h/c` | 48kHz 下跟随0–1的 amount；初始化指定5ms–2s时间常数，逐样本更新 |

初始化阶段调用 `oc_profile_read/compile`；调用方持有不可变数组。实时阶段将平滑 amount 交给 `sa_voice_tick_shaped_body`，每个谐波贡献乘 `1 + amount*(gain[h]-1)`，左右使用同一正增益，并在完整声／低频求和前应用。调用方保证数组至少有 `bank->harmonics` 项、有限、正且不超过16。加载与编译均在音频回调外，逐样本路径无分配或文件I/O。

amount=0或数组为NULL精确旁路；接口校验失败不推进voice。`VslOscColour_checks`用解析声源检查幅度、左右相位、低频分量和随机状态，并检查事务载入与单调跟随。

当前只有 `experiments/state_colour_v2/probe.c` 调用新接口。驾驶、UI及行程参数未接入此声线轴。A的短起落配方仅为诊断，自动扫频控制尚未达到0.5dB精度，详见[工况声线诊断](../../research/工况声线诊断V2.md)。
