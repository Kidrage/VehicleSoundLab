# 变速与统计纹理诊断

用已知声源及原C声源的固定／扫频、纹理关闭／开启配对，区分有限频带观察、确定性声线插值和现有随机纹理。输出是诊断，不是新的发动机预设。

- `fixtures.py`：无调制、共同调制、左右／频带差分调制；远离边界、跨边界、288阶密集谐波三组解析声源。
- `observe.py`：复用原完整频谱矩阵与包络描述，PC1同时报告绝对方差和标准差；近零协方差不报告比例。
- `run_joint_motion_controls_v1.py`：19已知对照先行，再经已审计门槛调用冻结原`local_atlas_export.exe`，输出16条原C诊断。
- `audit_joint_motion_controls_v1.py`：独立标量／复指数波形、Welch／反序CSD、DFT、OLS／协方差／有向滞后积；C另核全部CSV时钟及稀疏随机声源。
- `review_joint_motion_controls_v1.py`：两个科学图和12组有符号对数协方差预算，保留负项。
- `package_joint_motion_controls_v1.py`：检查670份原C/H、82份参数和F2文件，保留全部尝试并冻结。

真实配对复用同一`SaVoice`，没有另写驾驶器。这里是声源层诊断，不经过完整驾驶链；完整链仍用`experiments/joint_capture_v1`。从平均声线到开启纹理后的差异不是一个独立物理噪声源，也不能直接移植到细节层。声源／驾驶控制／空间处理边界保持，未增加房间处理。

详细步骤、结果和失败记录见[研究说明](../../research/变速与统计纹理分离诊断V1.md)。
