# 驻车片段声源检查

这是独立离线宿主，直接复用 `sound_dna`、`dna_atlas` 与现有 WAV 写入器。它不进入驾驶 UI，不更改驾驶控制器，也不定义新的状态音色。

- `trajectory.c/.h`：非实时读取相对样本位置与声学 Hz；校验边界、顺序和有限值，逐样本线性取值，不外推。
- `probe.c`：非实时加载模型，初始化同一组 atlas OSC；保持原有 18ms 跟随、相位插值和统计调幅，写 FLOAT L/R 及实际音高遥测。
- `tools/run_state_passage_v1.py`：构建、已知 OSC 对照、错误轨迹拒绝、旧回归、冻结路径复用、录音切片与试听文件检查。

```powershell
cmake -S experiments/state_passage_v1 -B build-state-passage-v1 -A x64
cmake --build build-state-passage-v1 --config Release
.\build-state-passage-v1\Release\state_passage_probe.exe `
  trajectory.txt output.wav trace.csv 1 48271 8 `
  'voices/exterior_anchors_v1/A Stationary Low.model' `
  'voices/exterior_anchors_v1/A Stationary Lower Mid.model' `
  'voices/exterior_anchors_v1/A Stationary Upper Mid.model' `
  'voices/exterior_anchors_v1/A Stationary High.model'
```

轨迹每行 `frame root_hz`，第一行为 frame 0，最后一个位置是输出的排他终点；48kHz、最长 180 秒。不导入音频样本、原片段包络、踏板或 RPM。输出目录应预先存在，使用新文件名。

实录例子仅为训练片段内的粗音高声源诊断。旧局部峰值路径连通，但长段相位资格未通过；不能据此认定发动机时钟、真实负载或完整驾驶状态已经标定。没有复制录音响度包络，参考与 DNA 声层数量不同。保持已认可移动尾排 DNA／低频与这些驻车实验模型分离。
