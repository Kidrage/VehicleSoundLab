# 谐波间残差 OSC V1

2026-11-11。本轮将上一轮观察到的高频能量缺口做成独立 C 声层。**平均频带能量得到补偿，是否更自然仍待听评。** 已认可的 A 移动尾排 DNA／相干低频、已有驾驶宿主和旧版本保持原样。

## 方法与模块

此前四周期 Hann 分析仅读中心谐波，对理想宽带噪声仅保留约 3/8 功率，不能通过整体放大 DNA 修复。本轮分别使用 A 驻车车外 Upper Mid、E 高转车内 Lower 的冻结观察和同一 C 核生成音，按 1.2–8kHz 的八个频带计算左右功率及复交叉谱。

每带取 `参考功率 − 已表示功率` 的非负部分。交叉谱差额转换为复相关，若幅度超过 1，则裁至可实现的单位圆内。A 有 4/8、E 有 3/8 个频带触发该裁剪；它表明独立相加的剩余声层不能完全修复原 DNA 的所有声道关系。本轮差额并非严格的逐样本谐波／噪声分离，也不直接等于进气、风声或机械源。

`modules/sound_residual` 用 512 个密集正弦 OSC 持续生成这份剩余谱。每频带包含共享／独立两组，种子决定初始频率与相位，模型没有 PCM 或录音时间轴。当前没有时变随机包络拟合，固定频率叠加仍可能产生可听拍频或砂感，需要单听与混音判断。

```mermaid
flowchart LR
    R[冻结录音观察] --> F[八带功率与左右交叉谱]
    D[同一C核的DNA输出] --> F
    F --> P[独立残差 profile]
    P --> O[sound_residual<br>共享／独立正弦OSC]
    D --> M[同增益对照混音]
    O --> M
    M --> A[离线stereo试听]
```

`profile.*` 管模型；`oscillator.*` 管持续声源；`voice.*` 管控制与独立时钟；`experiments/residual_osc_v1/probe.c` 管文件导出。离线拟合的读取、谱测量、模型编译、试听输出分别在 `tools/residual_osc_v1/{sources,spectrum,fit,review}.py`。模型副本在 `voices/residual_osc_v1`，未加入驾驶默认音色列表。

## 验证结果

| 观察 | 原 DNA 八带功率差范围（dB，L/R） | 加残差后最大绝对差（dB） | 混音复相关最大误差 |
|---|---:|---:|---:|
| A 驻车车外 | −5.08～−2.47 | 0.145 | 0.0047 |
| E 高转车内 | −3.45～−0.25 | 0.172 | 0.1356 |

这些是同一训练观察和当前种子的频带统计，不是未见片段泛化或感知相似度。E 的声道关系仍有偏差；两组仍是同一 V10 家族的不同录音情境，未验证多款发动机。

- 三个种子的已知 stereo／mono 模型验证通过：功率误差小于 0.5dB，复相关误差小于 0.04；mono 两声道逐样本相同。
- C 契约覆盖分块确定性、非法控制／模型拒绝、事务读取、零增益时钟和种子隔离。原系统加本模块共 **31 项 CTest 通过**，已有 C/H 字节保持不变。
- 0.9／1.0／1.1× 均持续生成 8 秒，变调不改变时长；原 DNA 样本保持相同，混音为逐样本加法。尚无本模块实际设备预算或长时运行结论。
- 试听页 10 个音频的 HTTP／本地文件载入、默认停止、互斥播放、全部停止和窄屏布局检查通过；静音浏览器检查不构成听感验收。

本轮只完成独立残差声源和离线混音，没有接入 `atlas_drive`、换挡／回火状态、独立低频、NVH 或 7.1.4。将来对象路由放在适配层；录音 L/R 相关性不能直接解释为物理声源位置。

## 试听与复现

[试听页](http://127.0.0.1:8789/research/谐波间残差OSC_V1.html)：A／E 分别提供录音短参考、只听 DNA、残差 50%／100% 和残差独奏。统一输出增益 0.25、5ms 首尾淡化、PCM24，没有逐条归一化／压缩或额外 EQ。新增声层会提高总能量，本对照不能排除响度偏好；若方向成立，再做响度匹配复核和动态包络拟合。

入口均接受 `--help`，使用可导入 `numpy/scipy/soundfile` 的 Python。先以 `Build-System.ps1` 构建，再依次运行：

```powershell
python tools/run_residual_osc_v1.py --workspace E:/VehicleSoundLab --probe E:/VehicleSoundLab-Git/handoff-build/bin/Release/VslResidual_probe.exe --out E:/VehicleSoundLab/references/analysis/residual_osc_v1/fitted
python tools/verify_residual_osc_v1.py --workspace E:/VehicleSoundLab --probe E:/VehicleSoundLab-Git/handoff-build/bin/Release/VslResidual_probe.exe --fitted E:/VehicleSoundLab/references/analysis/residual_osc_v1/fitted --out E:/VehicleSoundLab/references/analysis/residual_osc_v1/controls
python tools/make_residual_review_v1.py --workspace E:/VehicleSoundLab
```

输出目录和页面必须尚不存在，复做须使用新的工作区／目录。输入依赖 `baselines/exterior_anchors_v1` 与 `baselines/drive_evidence_v1`，模型、原观察和已有生成音均核对冻结清单 SHA256。`residual_osc_v1_summary.json` 绑定代码／模型／二进制／报告／试听与 CTest 留痕；冻结包由 `tools/freeze_residual_osc_v1.py` 生成。已有 Release 不包含本轮新增证据。
