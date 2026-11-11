# 驾驶监听传输包络

`am_render_init/set/process` 包装 `atlas_drive`，增加独立的10ms启动／停止淡化。发动机点火、熄火和挡位仍是 `AdControl` 输入；停止监听只终止本次监听，重新开始会初始化新的模拟。停止淡化一旦开始不会反向恢复。

模型、bank与独占 `VslEngine` 由宿主管理，无逐样本文件I/O／分配。DNA和对象捕获在传输淡化前，设备输出在淡化后。此库支持stereo／12通道；Windows宿主另限定stereo。

`experiments/atlas_monitor_v1` 分为 `models.*`、`audio.*`、`ui.c`：非实时事务验证，先停流再提交模型，重建bank指向长期存储；音频线程拥有驾驶／DSP，UI只提交输入。采用帧控制记录仅是有界调试证据，不是旧take协议或完整的用户录制格式。
