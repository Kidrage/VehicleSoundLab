# 同A启动车内细节探针

`probe.c`复用原`atlas_drive`、唯一驾驶器、单锚点DNA／残差库及启动／接火层，导出七条音轨和驾驶CSV。所有实时声源内核保持；不是另建合成器或驾驶器。

```powershell
cmake -S experiments/startup_detail_v1 -B build-startup-detail-v1 -A x64
cmake --build build-startup-detail-v1 --config Release --target startup_detail_probe --parallel 4
```

参数：`startup_detail_probe A.model early.start bloom.cb detail.residual PREFIX amount0..1 channels2|12 starts|hold SEED`。

- `starts`：两次启停，共6秒；`hold`：启动并持续，共10秒。
- 两者启动量50%、接火量50%、主增益0.25，细节量单独控制；模型／驾驶映射只适用本研究语境。
- 输出`mix/raw/dna/startup/catch_bloom/residual_raw/residual.wav`和`trace.csv`，已存在文件则拒绝。

新C宿主只作离线比较，未更改原生UI或schema5行程。实际量0回归、分轨／2与12一致及三seed统计见[研究及留痕](../../research/启动车内细节V1.md)。
