# 可变密度残差 OSC

独立实验模块，48 kHz、double stereo；未接入驾驶、监听或行程默认链。它复用 `sound_residual` 的谱矩模型和振荡器类型，不修改旧模块的布局、常量或声音。

| 文件 | 责任 |
|---|---|
| `carrier.h/.c` | 校验逐频带载波数，建立共享／独立正弦、复 L/R 权重，推进相位与周期归一化 |
| `voice.h/.c` | 拥有运行状态，校验音高／增益，以18 ms跟随控制，按块持续生成 |
| `CMakeLists.txt` | 声源库；只链接旧 `sound_residual`，不引入设备／UI／驾驶 |

`rd_voice_init(voice, profile, counts, seed, pitch, gain)` 复制所有运行所需数值，成功后可释放 profile 和 counts。`counts` 是独立的逐频带数组，允许8–256；不重解释旧模型的 `partials` 字段。旧语法的读取／验证仍由 `sr_profile_read` 负责。

`rd_voice_set` 接受0.90–1.10倍音高、0–1增益；无效控制和无效初始化保持原状态。`rd_voice_process` 输出交错双声道，增益0时仍推进时钟。调用者在音频线程外预分配 `RdVoice`；其最大存储约512 KiB，避免在Windows小栈上临时声明。

频带功率按载波数分摊，L/R使用共同载波与独立支路实现复相关。沿用旧随机数、分层选频、64帧调谐和1024帧归一化；全部频带设32时，输出及活动载波状态与旧核精确一致。

处理函数无分配、文件、设备、UI或空间操作。内核不识别发动机状态，也不声称把录音拆成物理噪声。更密的固定频率仍可能产生拍频；载波数增多不等于自然度提高。技术证据和范围见 `research/可变载波密度V1.md`，独立宿主见 `experiments/residual_dense_v1`。
