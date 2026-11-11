# Vehicle Sound Lab

Windows C11 声浪工程。仓库包含驾驶 DSP / App 0.20.0、独立 Sound DNA V1、低频轰鸣 V2 历史对照，以及新 DNA／相干低频联合监听、源码、测试、模型和交接文档。

![系统总图](handoff/系统总图.png)

## 构建和运行

安装 Visual Studio 2022 的「使用 C++ 的桌面开发」工作负载（MSVC x64、Windows SDK）和 CMake 3.21+。从工程根目录的 PowerShell 执行：

```powershell
.\Build-System.ps1
.\Launch-System.cmd rebuilt
```

构建脚本会执行 27 项 CTest（原25项加新DNA／空间接口、监听混音验证）。运行入口可打开驾驶、DNA 监听、低频对照与新声源联合监听，无需 Python 或 Max。新联合监听也可直接运行 `Launch-New-Monitor.cmd`，默认停止与直送组合，支持音高／低频／宽度／房间／电平调节。驾驶支持录制回放、实时立体声和离线 7.1.4 导出。旧 0.15.0 回退版本随本地交接包提供。

## 完整素材与开发证据

原始录音、清洗音轨、48 个冻结版本和全部渲染见 [完整交接 Release](https://github.com/Kidrage/VehicleSoundLab/releases/tag/handoff-2026-11-11)。[下载、校验和恢复说明](handoff/素材下载与恢复.md)。

## 接手代码

- [算法说明](handoff/算法说明.md)：声纹建模、OSC 合成、工况分层与实时接入的简明说明。
- [C 模块和接口](handoff/C模块与接口.md)：驾驶状态、实时 DSP、宿主和离线工具之间的边界。
- [工况与声层](handoff/工况与声层.md)：怠速、加速、巡航、收油、换挡等八种工况的分层响应。
- [开发留痕](handoff/开发留痕.md)与[阶段索引](handoff/阶段索引.csv)：历次方案、验证和听评。原始录音、冻结快照、旧版二进制和渲染音频由本地交接档案提供；旧试听和历史实验需要恢复相应证据。

驾驶 0.20.0 是功能主线；独立固定相位 DNA 在一个 V10 情境获认可，低频 V2 听评未通过。[研究续接](handoff/研究续接.md)记录了下一步：提取与发动机同步的低频，验证相位和包络，再按同等低频响度对照试听。

后续研究：相干低频 V1 获得“发动机感／厚度改善”的固定情境听评。新 [DNA／低频空间适配器](modules/dna_scene/README.md)已将两者接入同一 C 对象渲染链，保留干声、独立层和十源分轨，支持离线立体声／12通道；空间听评和完整驾驶工况接入尚未完成。新研究不在上面的冻结 Release 中，详见[本轮记录](research/DNA空间接入V1.md)。

新 [联合原生监听](research/联合声源原生监听V1.md)已加入简洁WindowsUI，底层混音见 `modules/scene_monitor`，宿主见 `experiments/scene_monitor_v1`。实际设备静音验证、控制采用帧离线重合成和程序内控件自测通过；用户连续听评、跨RPM／负载及完整驾驶接入仍待完成。
