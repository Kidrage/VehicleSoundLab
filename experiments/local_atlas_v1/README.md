# 局部多锚点离线入口

本实验仅提供模型拥有权、控制轨迹和文件导出。合成使用原`dna_atlas/SaVoice`，驾驶检查使用原`atlas_drive`；没有第二套OSC、驾驶器、设备或空间实现。

| 文件 | 职责 |
|---|---|
| `assets.h/c` | 非实时读取UTF8模型清单，拥有1–8份参数并绑定原SaBank；失败保持原对象 |
| `schedule.h/c` | 非实时读取有界逐帧控制事件；实时循环只读已验证事件 |
| `input.h` | 拒绝带符号／溢出的十进制整数 |
| `probe.c` | 以事件边界拆分块，调用原SaVoice，写FLOAT WAV／遥测CSV／元数据JSON |
| `checks.c` | 模型／轨迹失败事务及bank借用指针检查 |
| `driver_checks.c` | 原唯一驾驶器的2／12通道声源、六干声总线及状态精确检查 |

清单第一行`VSL_LOCAL_ATLAS 1 模型数 对齐阶数`，随后每行一个UTF8模型路径，允许空格。模型按根频率严格递增；宿主负责同车型／同观察语境，数值校验不能识别录音身份。加载使用显式带限接口，保留全部系数校验和原载波渐隐。

轨迹第一行`VSL_LOCAL_ATLAS_TRACE 1 总帧数 事件数`，随后每行`帧位置 根频率Hz 细节0..1 增益0..1`。固定48kHz、不超过60秒／12001事件，第一事件在0帧，事件帧严格递增且小于总帧数；根频率0..1000Hz。事件之间保持目标值，原声源18ms跟随；根频率0时宿主应以增益静音。

```text
local_atlas_export manifest trace output_prefix seed block_frames
```

输出`output_prefix.wav/.csv/.json`；拒绝已有输出。文件写入位于离线宿主，不进入音频回调。seed为非零uint64，block为1..512。CSV按200Hz及分支切换采样，不能当作全样本波形证明。

独立构建与检查：

```powershell
python tools/build_local_atlas_v1.py --workspace E:\VehicleSoundLab --out 新证据目录
```

脚本生成解析已知输入，运行两项`local_atlas_*`CTest；后续`run_F3_local_atlas_v1.py --stage known`核查完整已知波形及坏输入，再允许`--stage source`读取冻结声纹。每次使用新证据目录。原70项及共享DSP未改，不重复整套；本实验尚未接实时目录／owned preset／take。

当前实录研究与限制见[连续局部声纹库V1](../../research/F3连续局部声纹库V1.md)。
