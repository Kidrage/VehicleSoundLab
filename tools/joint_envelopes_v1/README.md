# 完整频带联合包络

离线读取原始时间片段，复用 `native_regions_v1/spectrum.py` 的完整双声道频带矩阵；这里不使用区域划分或波形相减。

- `controls.py`：静音、稳态、共同 AM、不同频带／声道 AM、无 AM 升频的解析控制。
- `features.py`：左右逐频带 dB、时间直线趋势、原始与去趋势协方差／有方向滞后积、ILD 和复数频谱相干。
- `run_F3_joint_envelopes_v1.py`：已知控制先行，原样读取已批准 F3 两段三秒片段，记录哈希与保护项。
- `audit_F3_joint_envelopes_v1.py`：独立原始读取／解析输入、Welch-CSD、显式 DFT、标量 OLS／协方差／滞后积核查。
- `review_F3_joint_envelopes_v1.py`：原生包络、去趋势关联和 ILD；不导出运行预设。
- `package_F3_joint_envelopes_v1.py`：冻结源码、原生数组、失败尝试及结果；`--verify` 独立复核清单。

时间趋势与去趋势值都保留。去趋势不等于分离出了随机机械调制；三秒片段不能证明平稳性或通用发动机动态。原声功率、左右平均差异没有被归一化，图中去均值仅供比较变化。均值频谱相干与包络相关是不同量。

所有工具显式指定数据 `--workspace E:\VehicleSoundLab`，尝试目录必须新建。详见 `research/F3完整频带联合包络V1.md`。
