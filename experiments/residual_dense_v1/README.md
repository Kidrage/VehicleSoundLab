# 可变载波密度：独立 C 宿主

不改根构建／驾驶默认。构建：

```powershell
cmake -S experiments/residual_dense_v1 -B E:/VehicleSoundLab/build-residual-dense-v1 -G "Visual Studio 17 2022" -A x64
cmake --build E:/VehicleSoundLab/build-residual-dense-v1 --config Release
ctest --test-dir E:/VehicleSoundLab/build-residual-dense-v1 -C Release --output-on-failure
```

`checks.c` 验证32条旧核样本／状态兼容、多分块、mono、模型拥有、无效调用事务和静音时钟。此构建有1项CTest；统一工程仍为40项。

```text
residual_dense_probe PROFILE OUTPUT SECONDS PITCH GAIN SEED PEAK BLOCK
```

`PEAK` 为0时直接调用旧 `sr_voice`；32／64／128／256调用新 `rd_voice`，逐带数量取 `max(32,min(256,ceil(带宽Hz × PEAK / 2000)))`。这是实验宿主规则，内核支持独立逐带数量。

`BLOCK` 选240／512，时长大于1且不超过60秒；输出FLOAT WAV。`OUTPUT` 为 `-` 时只计时而不写文件。计时只包围process调用，排除首1秒，报告块中位数／P95／最大值／超时和校验量；它不是设备或整个驾驶系统的实时资格。

复做证据应给脚本新的输出目录：先运行 `tools/build_residual_dense_v1.py`，再运行 `tools/run_residual_dense_v1.py`。后者固定原50%高频工程候选、DNA和低频，不逐密度重拟合或补偿响度，保存所有实际命令／源码。结果说明见 `research/可变载波密度V1.md`。
