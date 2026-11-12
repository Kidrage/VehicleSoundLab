# 左右声纹：离线模块

这些工具测量录音的统计传递关系，不进入音频回调，不识别物理声源，也不输出可直接加载的驾驶模型。

| 文件 | 责任 |
|---|---|
| `model.py` | 归一化谱矩、PSD子频格、父级先验、训练内复杂度选择、双向检验 |
| `controls.py` | 已知mono／独立／稳定滤波延迟／半段反转控制 |
| `oracle.py` | 从原始谱功率独立逐项求和，核对模型／误差及共同增益、交换声道不变性 |
| `components.py` | 联合、仅复交叉、仅平衡三类PSD候选；两类误差分别限制 |
| `budget.py` | 独立叠加的半正定条件、DNA功率边界、旧裁剪误差、已知矩阵控制 |

数据依赖已冻结 `reference_audit_v1` 原始Welch块，以及 `residual_osc_v1/sources.py` 的A驻车／E车内冻结参考与真实C输出。共同响度只在谱矩统计中除去；不改源音频，不把车内关系移到车外。

CLI依次为 `analyze_stereo_field_v1.py`、`analyze_stereo_budget_v1.py`、`detail_stereo_field_v1.py`、`analyze_stereo_components_v1.py`；各传 `--workspace` 和尚不存在的 `--out`。`finalize_stereo_field_v1.py`核对全部执行／来源、旧残差模型复现与442份C/H，`freeze_stereo_field_v1.py`冻结已提交源码和证据。报告说明见 `research/左右声纹与叠加预算V1.md`。
