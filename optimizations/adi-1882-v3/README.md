# VehicleSoundLab1882算法优化V3

本目录是基于1882 MCPS对应ZIP的独立优化工程，直接在此目录使用 `build.ps1` 构建。

- [同版本整体与分模块性能报告](docs/validation/performance-report.md)
- [用户补充的板测数据：最高峰值1174.11 MCPS](docs/validation/adi-board-20261120.md)
- [逐模块PC计时数据](docs/validation/modules-pc.csv)
- [算法变化及声音取舍](docs/算法与取舍.md)
- [ADI集成与板测入口](docs/ADI_板测入口.md)

Git版本包含源码、生成后的运行时参数及验证数据；本次桌面交付中的试听WAV、PC二进制和ZIP留在本地。已验证PC处理耗时下降54.6%–67.5%；2026-11-20收到用户板测摘要，最高峰值1174.11 MCPS，未达到摘要中的700 MCPS门槛及原500 MCPS目标。启动与完整驾驶仍有按1 GHz预算统计的超时块。

基于用户新提供的1882MCPS版本。默认统一声源优化、原版solo、同输入A/B及PC性能报告见桌面交付目录。现已补充用户板测整体MCPS；逐模块板测、编译配置绑定及DSP导出试听仍待补齐，详见docs/ADI_板测入口.md。

Windows/VS2022：`./build.ps1 -Mode production -Test` 构建静态运行时并检查短FIR/正态噪声；`./build.ps1 -Mode generic -Test` 跑9项验证，原8项多实例测试在generic配置执行；`./build.ps1 -Mode profile` 生成模块插桩版；`./build.ps1 -Mode diagnostic` 生成内部模块solo诊断版。音频入口仍是vs_engine_process，48kHz/256frame。PC渲染在工程根目录运行：

```powershell
./build/production/bin/Release/render_cases.exe ./build/production/bin/Release/vsl_source_bridge.dll full 36 256 ./full.wav 1
```

VSL_AIR=0环境变量可渲染无空气对照；VSL_AIR_SWEEP=1可在full流程的5/10/15秒依次改air为0/0.3/1。VSL_PERF_FILE指定profile版模块CSV输出。浮点桥接ABI必须与C头文件匹配，原tools/vehicle_controller/native.py中的double ABI不适用于此FP32工程。离线资产已经随包生成；重生成需numpy/scipy并通过tools/design_assets.py --reference指定新1882基线。

有意的声音变化：取消独立机械敲击、低频不再独立随机调制、共振在无支持时休眠并10ms淡入、DNA128采样更新、怠速等功率混合和启动共享line/air参数。见docs/算法与取舍.md。用户可用VSL_LEGACY_MECHANICAL=ON恢复旧机械链，用VSL_DNA_TABLE_HOP=64比较DNA更新密度；两种配置都要重新测性能。
