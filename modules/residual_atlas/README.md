# Residual Atlas

同一组持续OSC按声学根频率插值各档残差谱，供新驾驶链使用。A驻车四档／E车内两档分别建库，音色待听评。

| 文件 | 职责 |
|---|---|
| `bank.h/c` | 非实时事务建库，复制profile，验证根频率递增及频带／密度一致。 |
| `voice.h/c` | `ra_voice_init/set/tick`；同一正弦云插值功率／复交叉谱，18ms跟随。 |
| `sound_residual/oscillator.*` | 复用初始化及共享cos／sin、独立cos；切换锚点不重新触发。 |

插值正半定2×2谱协方差，再分解声道权重，避免独立音源交叉淡化造成拍频或凹陷。密集固定频率OSC自身的拍频仍存在，真实时间包络尚未拟合。

根频率只选谱形，不将1.2–8kHz载波随RPM整体变调；发动机谐波由`dna_atlas`负责。这是工程假设；超界沿用端点谱，遥测保留覆盖不足标记。

处理期无分配、I/O或PCM。bank须不可变且长于voice生命周期。独立seed；零增益仍推进时钟。`atlas_drive`保留DNA／残差独立stereo及对象分轨，分别投影后只做一次空间渲染；不是由L/R识别物理缸列。

`AdConfig.residual_bank=NULL`保留原链；`AdMix.residual_gain`默认0。模型切换先停音再提交；旧take协议不在此处扩展。见[研究记录](../../research/驾驶细节分层V1.md)。
