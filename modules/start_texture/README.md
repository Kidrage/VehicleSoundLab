# 启动前段纹理候选

`profile.c/.h` 读取16带观察L/R谱功率、复相关和工程起落时间；`voice.c/.h` 复用 `sound_residual` 的正弦载波核，持续生成统计纹理。没有PCM、逐帧轨迹、片段循环或每次启动重置相位。新模块不代替连续Sound DNA。

`st_voice_set(gate, amount)` 接受唯一驾驶器提供的拖转许可；`st_voice_process` 输出原始／门控stereo。门控关闭和量为0时也推进相位。模型在初始化时复制进OSC状态，音频路径无分配、文件读写或空间渲染。

当前只有A车内36.65–37.12秒的实验模型：它包含混合机械与空间贡献，未识别纯起动机。静态谱形不保留原段内的时间演化，也未生成后续接火／低频。5ms起、35ms落是工程淡化，不是真实机械时间。

独立构建：`cmake -S experiments/start_texture_v1 -B build-start-texture-v1 -A x64`，随后Release构建、CTest。探针参数：`start_texture_probe MODEL old|new|held OUTPUT.wav RAW.wav TRACE.csv 4 SEED`。`old/new` 用同一个既有驾驶器做两次启动；`held`仅用于持续源检查。没有接入默认UI、录制协议或空间器。

见[研究与局限](../../research/启动机械纹理V1.md)。
