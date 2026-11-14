# 原生频谱区域观察

本模块只做离线观察，不生成声源或修改 C 参数。

- `regions.py`：冻结相位逆映射的局部斜率范围、288 阶频率区间、互斥 FFT 区域。
- `spectrum.py`：原始双声道频带矩阵、区域矩阵及计数。
- `controls.py`：稳态、升速、确定性 AM 和相关噪声控制。
- `../run_F3_native_regions_v1.py`：已知控制先行，再处理六段原生素材与 54 个 C 子段。
- `../audit_F3_native_regions_v1.py`：独立区间扫描、Welch/CSD、显式 DFT、已知包络与特征值核查。
- `../review_F3_native_regions_v1.py`：图表和完整频带左右观察值，不导出合成预设。
- `../package_F3_native_regions_v1.py`：保护项核对、所有尝试冻结与清单验证。

区间只表明在指定时钟和窗下是否可分辨；Hann 旁瓣仍存在，线间区域也不等于机械噪声。6 kHz 以上没有干净线间点时保留重叠，不调整时钟、阶数、窗长或 FFT 补零去制造分离。后续生成应利用更长原始片段的全频带联合左右变化，不把此处短包络当发动机动态规律。

运行时指定 `--workspace E:\VehicleSoundLab`，各工具 `--out` 必须是新的尝试目录；复核冻结使用打包器的 `--verify`。详见 `research/F3原生频谱区域与包络V1.md`。
