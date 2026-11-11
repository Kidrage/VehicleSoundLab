# Vehicle Sound Lab

Windows C11 声浪工程。仓库包含驾驶 DSP / App 0.20.0、独立 Sound DNA V1 和低频轰鸣 V2 监听，以及源码、测试、模型和交接文档。

![系统总图](handoff/系统总图.png)

## 构建和运行

安装 Visual Studio 2022 的「使用 C++ 的桌面开发」工作负载（MSVC x64、Windows SDK）和 CMake 3.21+。从工程根目录的 PowerShell 执行：

```powershell
.\Build-System.ps1
.\Launch-System.cmd rebuilt
```

构建脚本会执行 25 项 CTest。运行入口可打开驾驶、DNA 监听和低频对照，无需 Python 或 Max。驾驶支持录制回放、实时立体声和离线 7.1.4 导出。旧 0.15.0 回退版本随本地交接包提供。

## 接手代码

- [C 模块和接口](handoff/C模块与接口.md)：驾驶状态、实时 DSP、宿主和离线工具之间的边界。
- [工况与声层](handoff/工况与声层.md)：怠速、加速、巡航、收油、换挡等八种工况的分层响应。
- [开发留痕](handoff/开发留痕.md)与[阶段索引](handoff/阶段索引.csv)：历次方案、验证和听评。原始录音、冻结快照、旧版二进制和渲染音频由本地交接档案提供；旧试听和历史实验需要恢复相应证据。

驾驶 0.20.0 是功能主线；独立固定相位 DNA 在一个 V10 情境获认可，低频 V2 听评未通过。[研究续接](handoff/研究续接.md)记录了下一步：提取与发动机同步的低频，验证相位和包络，再按同等低频响度对照试听。
