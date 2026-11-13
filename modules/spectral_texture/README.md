# 连续细谱声源

把素材中提取的固定谱形，用新的高斯激励持续生成。`profile.*`校验滤波器及L/R比例；`voice.*`拥有编译核／随机数／卷积历史与预取缓冲；`io.*`独立链接，仅非实时读取`.sfir`。

```text
固定谱形系数 → partitioned_fir只读编译核
                                  ↓
每带独立新高斯激励 → 卷积历史 → 分带输出 → L/R比例 → Stereo
```

`sf_bank_create`复制所需系数／标量，成功后原profile可释放。`sf_voice_create`分配全部状态并完成profile指定的预热；多个voice可借用同一bank，bank须比它们活得更久。所有create/destroy都在音频线程外。tick/process不分配内存、不读取文件，所有频带始终推进。

内部激励按256帧提前生成，预热后的第一帧对应原Python相同样本位置；没有人为添加输出延迟。外层音量、状态gate或幅度控制应在当前输出帧应用。这一策略依赖激励是内部可生成的随机数，不能直接用作外部音频的零延迟IR处理。

每带使用原`resonant_detail/excitation`随机数，种子为`seed XOR (0x9E3779B97F4A7C15*(band+1))`。保存的是谱形滤波系数和声道比例，不是原音频／原包络时间轴。此处没有房间处理、频率／相位调制、周期事件、额外声场或细节AM；各频带也不等于物理声源对象。

当前F2实验复用已冻结6组8192系数及48000帧预热，主声线／幅度由`modal_texture`独立负责。近单声道比例保留原模型，未补造左右信息。声音参数和主观认可范围不因C移植通过而扩大。

独立构建：`cmake -S experiments/spectral_texture_v1 -B build-spectral-texture-v1 -A x64`，再Release构建与CTest。`fine_idle_probe`组合C主声线和C细谱，输出core／detail／mix；参数示例位于该实验目录，原OSC和幅度参数复用前轮实验。

实际5ms块的成本见本轮研究summary。单样本调用可保证声音连续，但计算集中在256帧边界，不能按单样本20.8微秒预算部署。整套驾驶负载、设备和长时调度仍需独立核查；本模块未接当前默认驾驶器／UI／行程。
