# C 模块与接口

从 `src/core/engine.h` 和 `src/core/engine.c::vsl_process_layout` 开始读驾驶主线；从 `modules/sound_dna/voice.h` 和 `experiments/sustain_monitor_v3/render.c` 开始读声纹实验。两条链路各有入口、模型和运行状态，交接总入口只负责启动。

后续连接层：`modules/dna_scene/{source,routing,scene}.*` 将新DNA／相干低频的独立voice接入现有空间API。入口为 `ds_scene_init/set/process`，离线宿主为 `experiments/dna_scene_v1/probe.c`；初始化借用独占的 `VslEngine` 存储，但不运行旧驾驶或旧DNA。`DsCapture` 分别提供两层raw／增益后观察、直送监听和十源分轨。详见[接口边界](../modules/dna_scene/README.md)。本次还没有完成驾驶工况接入。

实时联合监听：`modules/scene_monitor/render.*` 提供 `smo_render_init/set/process`，保持两层声源并平滑切换直送／空间。`experiments/scene_monitor_v1/{ui,audio,models,recipe}.*` 分别负责UI、设备控制快照、事务模型载入和配方；统一构建入口为 `VslSceneMonitor`。它是新声源监听宿主，没有接管旧驾驶状态机或take协议，详见[原生监听记录](../research/联合声源原生监听V1.md)。

新增实验驾驶链：`modules/dna_atlas/{bank,voice}.*` 在共同周期坐标内插值多个录音模型，`modules/atlas_drive/{control,render}.*` 调用唯一的原驾驶控制器、既有工况增益包络、可选旧程序事件和空间API。入口为 `sa_bank_init`、`ad_render_init/set/process`，离线宿主为 `experiments/atlas_drive_v1/probe.c`。不调用旧DNA渲染，不接管原take和UI。目前仅覆盖两档E高转车内模型，完整工况声纹及设备／听评未完成，详见[模块图与证据](../research/多锚点驾驶接入V1.md)。

后续同一 C 库已加入 A 驻车车外四档实验模型；宿主 `probe.c` 支持 `--anchor` 追加模型和 `--root-per-rpm` 显式映射。模型按录音位置分库，不混入已认可 A 移动尾排低频。新增离线坐标校正／抗混叠在 `tools/exterior_clock_v1/warp.py`，不进入实时核。转速标定、完整负载／工况、实时性能与听评仍待完成，见[四锚点记录](../research/驻车车外四锚点V1.md)。

## 驾驶主线：DSP / App 0.20.0

最新原生接入：`modules/atlas_monitor/render.*` 在新驾驶链外增加传输淡化，`modules/win_output/device.*` 负责stereo设备队列，`experiments/atlas_monitor_v1/{models,audio,ui}.*` 分开管理模型／音频线程／控件。入口 `am_render_init/set/process`；快捷启动 `Launch-DNA-Drive.cmd`。30项回归及短时实际静音设备／控件检查通过，源和控制采用记录可离线逐样本复现；长期稳定性、新工况音色和产品录制格式仍待完成。见[模块图与设备记录](../research/DNA驾驶原生监听V1.md)。

| 责任 | 主要 C 文件 | 读写边界 |
|---|---|---|
| 桌面 UI、预设、输入 | `src/app/main.c`、`drive_panel.c`、`driver_keys.c`、`tuning.c`、`preset.c` | 将控件和键盘映射为 `VslParams`。UI 不积分驾驶时间。 |
| 原生音频宿主 | `src/app/audio_device.c` | 48kHz、512帧块、事件驱动 waveOut、MMCSS。读取控制快照，在实际设备提交后提交 take 指纹。 |
| 车辆工况 | `src/drive/drive.c`、`lifecycle.c`、`shift.c`、`fueling.c` | 200Hz 控制更新；启停／接火、自动保挡／安全降挡、喷油资格。驾驶员踏板、有效节气门和离合传递分别记账。 |
| 力学与挡位 | `src/drive/powertrain.c`、`longitudinal.c`、`coupling.c`、`clutch.c` | 计算扭矩、车辆阻力和曲轴／车辆耦合。控制期更新 RPM、负载、车速和变速状态；非逐车实测。 |
| 工况到声层 | `src/core/orchestrator.c`、`events.c`、`src/profiles/voicing.c` | 独立声层包络与瞬态资格；修改分层平衡优先检查这里及对应 profile。 |
| DSP 总入口 | `src/core/engine.c`、`engine.h`、`types.h`、`modules.h` | 管理 `VslEngine` 内的实例状态。`vsl_init` → `vsl_set_params` → `vsl_process_layout`。控制周期和逐样本更新在此汇合。 |
| 转动、DNA与高阶声源 | `src/core/clocks.c`、`dna.c`、`high_orders.c`、`exhaust_spectrum.c` | 维护独立发动机／自定义音色时钟，生成排气左右源；旧 `.dna` 模型在这里载入。点火几何位于 `src/profiles/firing.c`。 |
| 低频机体 PAD | `src/core/pad.c` | 驾驶主线的现有机体轰鸣床；与独立 `modules/low_rumble` V2 是不同实现。 |
| 机械、空气与事件 | `src/core/excitation.c`、`mechanical.c`、`mechanical_modal.c`、`modal.c`、`nvh.c`、`events.c` | 进气、机械、空气、路噪、风噪和事件；转动、已点火和断油的资格分开。 |
| 试验声源及色彩 | `combustion.c`、`character.c`、`pressure_texture.c`、`structure_texture.c`、`response_shape.c`、`response_kernel.c`、`event_color.c`、`event_split.c`、`firing_source.c`、`pulse_kernel.c`（`src/core`） | 基于共享事件与包络的可选变化，默认声源仍为 Original OSC。切换时不能重设驱动时钟或其他随机流。 |
| IR 与空间 | `src/core/acoustics.c`、`src/spatial/objects.h`、`scene.c`、`propagation.c` | IR 返回进入 BODY；10 条源分轨在空间与主音量之前。空间映射输出 2 或 12 通道，传播为可选几何模型。 |
| 录制、回放和协议 | `src/session/take.c`、`parameters.c`；`src/io/take_file.c`、`take_render.c`；`src/app/takes.c` | 记录实际采用的控制事件帧，保存有效 DNA／IR、seed、DSP版本与指纹；使用同一引擎重新合成。0.20.0 为严格 VSLTAKE schema 5／38字段。 |
| 文件和离线导出 | `src/io/wav.c`、`file.c`、`render_session.c`、`drive_trace.c`、`scene_metadata.c`；`src/cli/` | WAV、场景导出、take导出、状态 CSV、十源分轨与场景元数据。设备监听为 stereo；7.1.4 已有离线 12 通道布局，未完成实车／实际扬声器听评。 |
| 配方与验证 | `src/profiles/`、`src/core/profiles.c`、`tests/`、根 `CMakeLists.txt` | 五套工程音色模板与独立参数表；不宣称五款实车均已拟合。源级约束、车辆状态、take、空间与设备行为有各自验证入口。 |

信号流：`VslParams` → `VslDrive` → 包络/时钟 → `VslObjectFrame` → `vsl_scene_tick` → 主音量／输出。10 个源为排气左右、进气、机体、机械、空气左右、事件、道路、风。12通道顺序：FL、FR、FC、LFE、BL、BR、SL、SR、TFL、TFR、TBL、TBR。`vsl_process_layout` 的可选 `stems` 是每帧交错的10源，不能从渲染后立体声反推。

控制时钟约200Hz，DNA／高阶系数更新每128帧，主要参数约18ms跟随；不同声层的工况包络有自己的时间常数。设备／文件／分析不要搬进逐样本核。当前源码版本不改；后续变更同时看 `AGENTS.md` 的采样、状态与协议约束。

## 独立音色链

| 模块 | C 接口与责任 | 宿主 |
|---|---|---|
| Sound DNA V1 | `modules/sound_dna/profile.*` 事务模型载入；`texture.*` 生成相关变化；`oscillator.*` 固定均值相位、变化幅度；`voice.*` 管理 `sd_voice_init/set/process` | `experiments/sustain_monitor_v3`；V10对照逐样本一致，Warm/Hollow是合成验证。 |
| 残差 OSC V1 | `modules/sound_residual/profile.*` 模型事务读取；`oscillator.*` 共享／独立正弦云；`voice.*` 管 `sr_voice_init/set/process`、18ms跟随与独立时钟 | `experiments/residual_osc_v1/probe.c` 离线导出；31项总回归通过。未接入设备／驾驶，待听评；不是物理噪声分离。 |
| 驾驶残差 atlas | `modules/residual_atlas/bank.*` 事务复制六档模型；`voice.*` 以同一OSC云插值正半定谱矩阵，`ra_voice_init/set/tick` | `atlas_drive`接入；新UI细节量默认0。DNA／残差／对象分轨独立，33项回归通过；不是完整负载／状态模型。 |
| 低频 V2 | `modules/low_rumble/profile.*`、`cloud.*`、`voice.*`；`lr_voice_init/set/process`；密集随机正交OSC、独立时钟和滤波 | `experiments/sustain_monitor_v4`；V2听评未通过，保留对照。 |
| 监听混音 | 两个实验目录各自的 `render.*`／`audio.*`／`ui.c`／`bank.*`／`smoke.*` | 控件、音色事务切换、独奏与设备。V4低频0与DNA监听逐样本一致。 |
| 历史实验 | `experiments/reference_osc_v1`、`reference_osc_v2`、`osc_density_v1`、`detail_osc_v1`、`sustain_osc_v1` 等 | 时间轨迹重建、固定音高统计声源、分离假设和试验对照；以对应冻结版本的说明为准。 |

两种新实验模型 `.model` 在各自库使用，生命周期内借用不可变 profile；声音处理不做文件读取、不回放素材，也不依赖 Python、Max。旧驾驶 `.dna` 与它们的格式不同；今后接入驾驶应新增适配和新版本，不能直接更名或覆盖旧文件。三层设计以独立源／控制为接口，IR、房间、声场在外层组合，避免同一录音传递重复叠加。

## 修改入口

| 任务 | 从哪里动手 | 首要回归 |
|---|---|---|
| 换挡／启停／喷油策略 | `drive/shift.c`、`lifecycle.c`、`fueling.c` 与 `profiles/` | 转动与点火资格、边界换挡、状态连续、已有 take 兼容性。 |
| 改某一声层 | 对应源模块及 `orchestrator.c` 的映射 | 独奏／分轨、零量旁路、其他声层和驱动状态隔离。 |
| 增加通用音色 | `tools/compile_sound_dna.py` 与 `modules/sound_dna` | 同种子可重建，模型事务加载、根音、变音高不变时长、听评。 |
| 恢复低频研究 | [研究续接](研究续接.md) | 相干提取与相同响度对照，先证据后接入。 |
| 改宿主或空间 | `src/app/audio_device.c` 或 `src/spatial/` | 设备速率／断流、2/12通道源分轨不变、录制回放。 |

所有当前 `.c`／`.h` 及用途分组见 `C文件索引.csv`。统一构建在 `handoff/CMakeLists.txt`，驾驶原始构建在根 `CMakeLists.txt`；其余实验各自有 CMake。完整历史材料按 `开发留痕.md` 与 `阶段索引.csv` 定位。
