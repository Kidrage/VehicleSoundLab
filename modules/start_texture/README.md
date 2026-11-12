# 启动前段纹理候选

`profile.c/.h` 读取16带观察L/R谱功率、复相关和工程起落时间；`voice.c/.h` 复用 `sound_residual` 的正弦载波核，持续生成统计纹理。没有PCM、逐帧轨迹、片段循环或每次启动重置相位。新模块不代替连续Sound DNA。

`st_voice_set(gate, amount)` 接受唯一驾驶器提供的拖转许可；`st_voice_process` 输出原始／门控stereo。门控关闭和量为0时也推进相位。模型在初始化时复制进OSC状态，音频路径无分配、文件读写或空间渲染。

模型版本1维持原单一谱形路径；版本2增加前／后两个PSD谱矩端点。`st_voice_position(0..1)`设置无量纲谱形位置，18ms跟随、每64样本更新合成系数；插值功率与复交叉矩，再分解成有效左右系数。载波频率不随此参数改变，避免额外扫频。两个版本均由`st_profile_read`事务读取。

当前只有A车内36.65–37.12秒的实验模型：它包含混合机械与空间贡献，未识别纯起动机。`voices/start_texture_v1`保留静态模型，`voices/startup_drive_v1`以该段前后半段作为两个端点；没有保存系数时间轴。仍未生成后续接火／低频。5ms起、35ms落是工程淡化，不是真实机械时间。

独立构建：`cmake -S experiments/start_texture_v1 -B build-start-texture-v1 -A x64`，随后Release构建、CTest。探针参数：`start_texture_probe MODEL old|new|held OUTPUT.wav RAW.wav TRACE.csv 4 SEED`。`old/new` 用同一个既有驾驶器做两次启动；`held`仅用于持续源检查。

统一链可选接入：`AdConfig.startup_profile`＋`AdMix.startup_gain`，正量必须提供模型；仅CRANK门控，谱形位置按既有拖转进度给定。入口`Launch-Startup-Study.cmd`使用独立构建、车内库、50%层量，默认停止。附加层保留stereo只路由一次到FL/FR；不进房间／传播／视角处理。当前录制schema5拥有模型并保存27字段控制，原schema4播放器保留。后续`Launch-Catch-Study.cmd`可在同A趋稳DNA上另加独立`catch_bloom`；本模块仍只负责启动前段。不是将另一视角的启动层默认覆盖到认可车外配方。

见[初版研究](../../research/启动机械纹理V1.md)及[统一链与证据](../../research/启动层统一驾驶V1.md)。
