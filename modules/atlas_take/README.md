# 新 DNA 驾驶行程

`AtTake` 拥有不可变模型资产和实际采用帧上的控制事件；`AtPlayer` 使用同一 `atlas_monitor` 重合成。它不保存录音／输出 PCM，不复用旧 `VSLTAKE`。

| 文件 | 责任 |
|---|---|
| `assets.*` | 深拷贝 DNA／残差／启动纹理／接火低频／有效对齐相位与查表；校验、内部指针绑定。 |
| `parameters.*` | 27 个语义控制字段，含五路辅助量、启动量及接火量；比较不依赖结构体 padding。 |
| `take.*` | 预分配事件、成功提交帧计数、停止边界、源／输出 FNV64。 |
| `player.*` | 在事件／停止帧切块，重建控制与淡化；2／12通道共用声源。 |

对象须先零初始化。`allocate/begin/valid/player_init/free` 都在非音频线程调用；模型完整性验证可能分配内存。开始录制需要新鲜第0帧，不能从中途DSP状态直接开始。初始化控制与第0帧实际采用控制分别保存，避免改变首次平滑状态。

实时顺序：`at_take_event` → 合成／计算源哈希 → 设备成功提交 → `at_take_commit`。失败块不计入长度；线程停止后 `finish` 裁掉未提交事件。上限10分钟、65536事件。宿主提前淡出；录制使用预分配内存，不进行文件I/O。

`at_player_process` 可接受任意块长；完成后 `verified` 比较源哈希及原布局输出哈希。12通道导出只改变空间布局，源哈希相同。它不是实际扬声器的测量结果。

当前 `.vslrun` schema5保存对象／立体声声床配置及可选启动／接火模型，共27控制字段。辅助对象、启动stereo和接火附加量逐帧纳入源哈希，记录／设备／播放器均预分配缓冲区，不存PCM。schema4匹配播放器保存在`catch_drive_v1/before/bin`，schema3在`startup_drive_v1/before/bin`，schema2在`system_status_v1`及`stereo_bed_v1/before/bin`；旧schema1继续用原冻结二进制，不做静默格式迁移。上述证据目录均位于本地`references/analysis`或对应冻结快照。

兼容性由DSP／控制／播放器源码、编译器及配置旗标的SHA256身份约束，文件另存于 `atlas_take_io`。保留相匹配的二进制；跨平台／跨编译器不保证浮点位级一致。FNV用于重建与意外损坏检测，不是数字签名。
