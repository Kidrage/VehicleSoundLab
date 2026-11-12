# C 模块与接口

当前[行驶完整配方统一驾驶](../research/行驶完整配方统一驾驶V1.md)：`drive_recipe/bank.*`拥有原相干LF／功率mask与非实时事务校验，`shape.*`根据实际下一采样根音／细节量撤去相应DNA功率，`voice.*`复用主DNA采样相位／锚点原点持续生成独立LF。`atlas_drive`独立量／机体包络／捕获与一次路由；`atlas_take`拥有参数，`atlas_take_io`schema8／29控制，LF raw与输出纳入源哈希。新增10份C/H、24接口／宿主／测试适配、506旧字节保持，共540；55项、84旧WAV和实际静音台架／踏板／2-12录放通过。原模型不改，真实怠速／完整加速仍未完成；以下保留历史阶段的接口范围。

最新[双声道细节统一驾驶](../research/双声道细节统一驾驶V1.md)：`drive_resonance/bank`拥有逐锚点Rdt／Rvs类型与参数，非实时堆暂存事务构造；`voice`复用同一DNA坐标／支持与原核，不加RPM时钟。既有分轨／驾驶包络／声床路由保持，schema7／28控制拥有系数与稳定证书；同一原生滑条和录放入口，默认0。530份C/H＝519旧文件保持＋10适配＋1新契约；53项、84旧音轨、三短设备录放／取消／2-12和13项自身UI检查通过。车内工程怠速有局部支持，PULL细节仍0；并非热怠速／加速音色完成。此段覆盖下文历史“未接驾驶／行程”。

新增[双声道连续共振核](../modules/stereo_resonance/README.md)：`profile.*`做非实时稳定证书校验，`voice.*`连续生成2×2跨延迟VAR／独立激励／SOS／18ms量平滑，独立`stereo_resonance_io/profile.*`事务加载。旧521份C/H不变，8新增、索引529；52项CTest、已知多阶／相位方向／声道交换及三48秒C统计核对通过。A启动后车内候选无PCM／新房间／驾驶／行程接入，600–850Hz缺口及热怠速／负载标定未解决，见[证据与限制](../research/低转双声道连续细节V1.md)。

最新[踏板状态核查](../research/踏板状态与细节覆盖V1.md)：`experiments/drive_resonance_v1/device.c --pedals`复用原驾驶输入／设备／行程；新增`inspect.c/.h`只在设备停止后离线导出分轨／状态，不进入实时库。521份C/H，518旧文件不变、1实验宿主适配、2新增。七种运行工况走通，但稳定850工程RPM怠速细节为0，加速也仅短暂支持；下一步需补参数与转速依据。

当前新增[drive_resonance](../modules/drive_resonance/README.md)：`bank`非实时拥有匹配锚点参数；`voice`预热／消费同一主DNA相位和周期原点，无独立RPM时钟。`AdConfig.resonant_bank`、`AdMix.resonant_gain`、`AdCapture.resonant_raw/resonant`连接同一驾驶／混音链；`atlas_take`拥有库、schema6／28字段及新增源哈希。原生研究入口复用滑条6并停用旧残差，默认0。519份C/H＝原511中492不变／19适配＋8新增；51项CTest、84旧WAV及短设备录放通过。仅A低转add候选，行驶35%完整配方及全RPM／负载标定仍未接通。

当前新增[完整声源监听适配器](../modules/resonant_monitor/README.md)：`rsm_render_init/set/process`负责借用模型、平滑、10ms启停、一次输出及分轨；实时无I/O／分配。宿主`models`拥有并非实时加载，`audio`复用`win_output`和成功提交帧调试记录，`ui`默认停止；没有新驾驶／行程字段。原500C/H字节保持，11新增、索引511；50项CTest及四次短静音设备重现通过。三配方8秒dry与既有C基准完全一致，音色未新增验收。

当前[完整配方接口](../modules/resonant_source/README.md)：`rss_profile_prepare`非实时向独立模型编译谐波功率替换；`rss_voice_init/set/tick`组合原DNA／匹配LF和连续共振细节，只预热细节，运行按同一DNA采样相位；`rss_output_frame`一次主增益／宽度及2／12前置声床。9组8秒完整混音、3组2／12对照及49项CTest通过，原492C/H不变、8新增、共500份。没有新原生／驾驶／行程字段或默认改动；此状态覆盖下面历史“无完整混音适配器”，仍不等于音色／完整RPM负载覆盖。

当前新增C接口：[连续共振细节核](../modules/resonant_detail/README.md)的`profile/envelope/excitation/filter/voice`只处理参数校验和连续细节；`resonant_detail_io/profile`负责独立非实时事务加载。`rdt_voice_tick`消费外部主声相位，不持有RPM时钟，不分配／I/O；模型整个运行期由调用者只读持有。参数与混合职责见[参数说明](../voices/resonant_detail_c_v1/README.md)。三个参数×三个seed细节核数值通过，48项CTest通过，现492份C/H（原478份不变、14新增）。**没有完整混音适配器／驾驶字段／UI／行程接入或原生听评**；下文历史“无C加载器”记录仅描述当时状态。

新增[加速诊断](../research/固定挡位加速核查V1.md)复用`experiments/state_passage_v1/{trajectory,probe}`与当前`dna_atlas`；没有新增C/H、控制字段或默认路径。Python的`acceleration_passage_v1/evidence`只绑定素材／模型／上下文，`diagnostics`只测宽频带预算；离线输入轨迹不接管统一驾驶器，音色未验收。

新增[低转离线配方](../research/驻车低转声源V1.md)仍复用原C DNA，未新增C/H。`tools/idle_texture_v1/{profile,envelope,power}`分别负责按实际根音派生参数、资格检查及任意周期的预算；连续生成仍调用原`resonant_detail_v1.voice`。新`voices/idle_resonant_v1/detail.json`不含PCM／时间轴，也没有C加载器／驾驶字段。原478份C/H保持，音色待评。

最新状态：用户暂留共振细节V1的35%，否决70%；中频保护V2不采用，停止继续调同一行驶片段。它们均是离线原型，**尚无该细节核的C加载器／驾驶接口**。现有`atlas_drive/render.c`调用同一200Hz控制器和`dna_atlas/voice.c`，怠速／加速使用同一C生成链；负载目前主要进包络，完整状态声纹未标定。见[实际完成度](../research/怠速与加速完成度V1.md)。原478份C/H保持。

新[共振细节替换](../research/连续共振细节替换V1.md)仅为分模块Python离线原型：`envelope`／`filters`／`voice`／`controls`分别负责弱能量形状、共振拟合与预算、持续生成、独立验证；`voices/resonant_detail_v1/detail.json`为纯参数快照，尚无C加载器。原C DNA核复用、478份C/H未改，驾驶／设备／行程没有新接口。听评成立后再按同样职责移入C，不把离线脚本写成实时接入已完成。

最新状态：共同微扰原生C未通过音色听评，用户补充离线／C均不足。[新诊断及计划](../research/DNA高频质感诊断与优化V2.md)优先修DNA高频过度周期化；没有新C模块或默认改动，原478份C/H保持。下文技术接入通过不能作为音色验收。

新增[共同微扰C接入](../research/共同微扰C接入V1.md)：`modules/phase_texture/motion.*`负责独立随机控制／样条，`voice.*`负责原幅度与同组谐波的共同相位适配。`DsSourceControl.phase_texture`为0–1轻量强度，`DsSourceConfig.phase_seed`为独立种子，默认强度0；`--phase-texture`研究监听打开轻量开关。478份C/H，466原件不变，47项CTest／短设备通过。旧玩家已存，驾驶器／行程未加新控制；原生听评待确认。

最新[启动细节原生接入](../research/启动细节原生接入V1.md)：`experiments/atlas_monitor_v1/models.c::am_models_load_variant`非实时事务装入同A细节，`ui.c`绑定既有细节量；新增`experiments/startup_detail_host_v1/{checks,ui_checks}.c/.h`只负责模型／资产和控件消息验证。原`src/`及`modules/`保持，472份C/H含3新增／5宿主验证修改；46项CTest及短设备／schema5录放通过。没有新增驾驶器、实时声源或协议。

新增独立[启动车内细节](../research/启动车内细节V1.md)：`experiments/startup_detail_v1/probe.c`复用原atlas／残差／唯一驾驶器及启停层；只新增1份离线宿主，原468份C/H及职责保持，现469份。Python的`startup_detail_v1/budget.py`校验左右可加差额，`controls.py`做已知矩阵／DFT核对。沿用SrProfile、RaBank和原渲染接口，没有改UI／schema5；11带新增量、600–850Hz为0。8条共增益试听待听评，三seed平均统计不能代替自然度。

当前接口以[接火低频统一驾驶V1](../research/接火低频统一驾驶V1.md)为准：`atlas_drive`可选`catch_profile`／`catch_gain`／`AdCapture.catch_bloom`，由唯一200Hz驾驶器CATCH调度，完整包络后DNA在互补重分配前输入，新层仅一次前置路由。`atlas_take`拥有启动／接火模型，schema5／27字段及新源哈希；旧schema4匹配播放器已保存。独立研究入口`Launch-Catch-Study.cmd`，接火量默认0%，音色仍待听评。45项CTest、108旧WAV字节回归、短设备与录放／2和12导出通过，现468份C/H。新增`experiments/catch_drive_v1/{checks,probe}.c`，八份接火内核C/H不改。以下按各阶段记录当时接口，不据旧版本描述判断当前集成状态。

新增[接火低频建立V1](../research/接火低频建立V1.md)：`catch_bloom/profile.*`校验模式与包络，`filter.*`固定带通，`envelope.*`共同beta／指数跟随，`voice.*`持续处理DNA并只输出附加量。唯一驾驶器的CATCH进度由独立离线宿主读取，未新增车辆时钟、随机源或空间器。`experiments/catch_bloom_v1`检查解析频响／包络／状态连续及两次启停／2与12前置一次路由；8模块＋2宿主C/H新增、旧456身份不变，现466份索引。尚未接默认实时UI／行程，也未获听评；不能把宽带颜色拟合叫物理车体分离或完整启动恢复。

新增同录音启动诊断：`experiments/startup_scene_v1/probe.c`复用原`atlas_drive`／唯一驾驶器／`dna_atlas`／`start_texture`，将A启动前段与新A趋稳DNA做两次启停、raw／层分轨和2／12导出；它仅是离线宿主。`tools/startup_catch_v1/{clock,slow_phase}.py`分开慢相位观察与独立局部核对，不进入实时链。旧455份C/H字节保持，新增1份、当前456份；原43CTest／UI／schema4身份不变。快速接火及新声音听评未完成，见[启动后车内DNA](../research/启动后车内DNAV1.md)。

当前[启动层统一驾驶](../research/启动层统一驾驶V1.md)：`start_texture/profile.*`兼容单／双端点谱矩，`voice.*`提供`st_voice_position`和持续OSC谱矩插值；`atlas_drive`新增可选`startup_profile`、独立`startup_gain`及`AdCapture.startup`。同一CRANK门控、载波不调频、stereo前置一次路由；`events`分开旧starter与transients，仅新模型存在时替换前者。`atlas_take`拥有模型、26字段与源哈希，`atlas_take_io`schema4严格拒绝旧身份，旧schema3播放器冻结。43项CTest与短设备／录放通过，现455份C/H；新增`experiments/startup_drive_v1/checks.c`，其余为明确接口适配。入口`Launch-Startup-Study.cmd`，未替换已认可固定情境或旧运行窗口；完整接火／低频与听评未完成。下文保留各阶段当时接口。

新增独立 `modules/start_texture/profile.c/.h`（谱矩与起落参数）和 `voice.c/.h`（持续OSC、门控、量跟随）。`experiments/start_texture_v1/probe.c`复用唯一驾驶器导出两次启动附加层，`checks.c`验证门控与声源隔离；仅新增6份C/H，旧448份不变，现454份。该层尚未进入默认UI／atlas／录制协议，也不含接火低频。见[方法与证据](../research/启动机械纹理V1.md)。

新增`modules/stereo_bed/route.c/.h`：观察L/R的一次宽度控制与2／12前置声床映射。`atlas_drive`的`AdConfig.scene_mode`0沿用旧对象投影，1保留DNA／互补低频／残差stereo，并只让辅助／事件进入原空间器；`AdCapture.observation/bed`可独立捕获。`atlas_take`／`atlas_take_io`现为schema3／25控制字段并保存模式，旧schema2播放器已冻结。当前448份C/H，见[集成与证据](../research/立体声声床接入V1.md)。

新增独立状态片段诊断：`experiments/state_passage_v1/trajectory.c/.h`负责非实时声学Hz轨迹的读取、验证和不外推取值；`probe.c`调用原`dna_atlas`持续生成并写实际音高遥测。它不进入默认驾驶链、不写驾驶器RPM。新增3份C/H，旧442份身份保留，详见[驻车局部对照](../research/驻车状态局部对照V1.md)与[独立构建说明](../experiments/state_passage_v1/README.md)。

最新[左右声纹／叠加预算](../research/左右声纹与叠加预算V1.md)只新增离线`stereo_field_v1/{model,controls,oracle,components,budget}.py`，不改C接口。细频传递的总误差会掩盖左右平衡回退，新分量族仅D两带通过；A/E独立叠加存在非PSD差额，不能自动加宽。当前`dna_scene::ds_route_frame`明确选左／右／mid为mono，再送排气代理；`atlas_drive`的原始L/R捕获与直送保留双声道，空间12通道分支并非完整stereo声床。后续适配需先定义观测声床／源对象与联合能量预算，保持唯一控制器和一次渲染。442份C/H及认可模型SHA不变，本轮未重编或重跑C测试。

新增独立[可变载波密度](../research/可变载波密度V1.md)：`modules/residual_dense/carrier.*`校验逐带8–256数量、生成共享／独立正弦和复相关；`voice.*`拥有数值状态、平滑控制和持续块生成。`rdt_voice_init/set/process`复用旧`SrProfile`谱矩但数量由独立数组提供，不改旧布局／常量；全部32条时输出／活动状态兼容。调用者在非实时预分配524352字节；处理不分配／I/O／空间／驾驶。`experiments/residual_dense_v1/{probe,checks}.c`只管导出／隔离计时与契约，未接默认宿主或行程。既有40项CTest＋独立1项通过，442份C/H索引保持旧436份职责／哈希。更密固定载波仍有拍频，不代表真实燃烧AM或已认可音色。

新增独立[高频密度C对照](../research/局部谱线与高频密度V1.md)继续使用原`sd_voice`／`sr_voice`，离线派生`voices/line_density_v1`模型并汇总C分轨；未改C接口或接入默认宿主。`line_density_v1/{measure,controls,profiles,review}.py`分开测量／已知控制／正增益编译／试听，后续不可把它理解成新实时混音器或已认可物理声源。三种子和实际WAV门槛通过，自然度仍待听评；现有云每带32有效共享载波的密度限制需另测，不能只看总分配数512。

当前统一链的简明图与认可范围见[算法说明](算法说明.md)；以下逐阶段接口记录保留原时点语境。最新[慢声线／谐波分配复核](../research/慢声线与谐波分配V1.md)仅新增离线`harmonic_allocation_v1/{observe,controls}.py`，没有C接口变化。失谐纯音反例禁止把平均相位占比直接当残差份额；四项rect1门槛仍失败，不据此晋级模型。

最新离线复核：[因子功率与窗口复核V1](../research/因子功率与窗口复核V1.md)。`factor_power_v1/{moments,simulation,windows}.py`分别处理数学矩、独立模拟／重建、窗口观察；未增加C接口。短片段随机功率偏差和单窗失谐混淆需分别处理；原AR8门槛未改，也没有据此接入驾驶或默认音色。下一步先固定跨窗口一致的慢幅度与相干／残差能量预算。

新增离线时间因子实验：[幅度时间模型与时钟敏感度V1](../research/幅度时间模型与时钟敏感度V1.md)。Python的`magnitude_timescale_v1/factors.py`独立拥有拟合／平稳历史，`render.py`消费因子并维持固定相位OSC；没有C或驾驶接口变更。AR8候选未过16秒功率门槛，不接默认声线。继续保留原残差AR1、时钟／低频与外层空间边界，先核对短窗／时钟混淆和有限功率预算。

最新离线测量：[共同响度与声线变化V1](../research/共同响度与声线变化V1.md)把log频带包络分为共同项／相对声线项，并以窗口／去趋势和已知控制检验；独立标量／带间比例／DFT核验1707条记录。它没有新增C接口，也没有把数学分量映射成物理源或驾驶状态。持续随机幅度与唯一驾驶控制器的慢包络仍须分开维护，先判定既有候选听感，再决定独立C声部。

新增离线研究见[高频时间细节V1](../research/高频时间细节V1.md)：Python的`harmonic_magnitude_v1/{model,legacy}.py`分别承担直接幅度统计／持续OSC和旧配方重建，测量另在`temporal_texture_v1`。它尚未成为C模块；现有`sd_voice`、`dna_atlas`、驾驶、空间和take接口均未修改。若听评成立，沿独立profile／幅度状态／OSC／宿主边界实现实验C声部，再做控制与实时资格；不能把当前离线通过解释成新驾驶音色通过。

参考方法更新：[V6公开链路核查V1](../research/V6公开链路核查V1.md)给出上游分层图及到本地模块的职责映射。公开连续DNA、可选启动采样、历史纹理循环分别核对，未直接复制上游声源。[立体声相位斜率V1](../research/立体声相位斜率V1.md)未建立通用延迟改善；没有新增实时模块或参数。436个C/H与已有接口保留，下一步先比较录音和现有生成器的时间／带间统计，避免把普通拍频重复加入AM。

数值边界：独立 `modules/rt_numeric/scope.*` 管理当前线程的局部FTZ／DAZ和完整MXCSR恢复；`atlas_drive`／`atlas_monitor`的process薄包装覆盖声源、空间与传输淡化，支持嵌套／失败退出。40项CTest、156条音轨（最大误差1.18e-38满幅）、控制轨迹、固定DNA字节及实际静音设备／行程通过。`.vslrun`身份已绑定该模块；其他架构为空操作。A仍有5ms超时，见[模块图与验证](../research/数值作用域V1.md)。

性能更新：`sound_dna/texture.c/.h`新增 `sd_texture_prepare_batch`，`dna_atlas/voice.c`调用。只有维度、时钟和完整随机状态已经相同的锚点才共享随机创新；各自AR／RNG状态保留，不兼容时串行推进。39项CTest、15场景哈希、4组轨迹、固定DNA整WAV字节和短时静音行程回放通过；A／E交替离线中位数耗时降低5.39%／3.08%，仍有5ms超时。性能探针与25组完整状态契约位于 `experiments/atlas_perf_v1`；当前没有幅度缓存，也没有生产FTZ／DAZ。见[模块图与证据](../research/C性能核查V1.md)。以下保留各阶段接口记录。

新增独立 `modules/residual_motion/{profile,envelope,carrier,voice}.*`：分别负责模型校验、幅度统计变化、同一OSC推进和声部控制。只改变可选残差层幅度，raw与0量保持旧声源逐样本一致；没有接入驾驶／UI／take，不改已有C文件。38项CTest及已知stereo约束通过，但同一短实录的统计误差下降最多0.67%，自然度提升尚未建立。见[模块图与边界](../research/残差幅度细节V1.md)。

最新统一驾驶链增加 `modules/drive_aux/{motion,voice}.*`：前者把唯一驾驶控制器适配到独立曲轴／喷油门，后者持续运行既有机械模态／NVH，分出进气、机械、排气空气、道路、风五个工程声层。五个量默认0，不调用旧DNA／PAD／排气激励器；新增raw／增益后对象及直送捕获，外层只渲染一次空间。原生UI用一个声层选择框＋共用滑条分别调五层。行程当前25字段、`.vslrun` schema2，辅助对象纳入源哈希；旧schema1用冻结播放器。见[模块图与本轮验证](../research/驾驶辅助声层V1.md)。以下原接入记录按各阶段描述理解。

新增独立诊断：`modules/osc_colour/{profile,envelope}.*`分别负责非实时谐波增益编译和0–1平滑，`dna_atlas::sa_voice_tick_shaped_body`在同一谐波贡献上施加L/R共同幅度形状，再取完整声／LF。默认接口精确旁路，只有 `experiments/state_colour_v2`离线宿主调用；未映射驾驶／UI。35项已有测试及新增契约通过，19条冻结驾驶分轨与控制CSV一致；扫频跟踪仍未达0.5dB精度，候选仅限诊断。见[模块图及边界](../research/工况声线诊断V2.md)。

新增行程：`modules/atlas_take/{assets,parameters,take,player}.*`分别拥有模型、20字段、成功提交事件／帧数和重合成；`modules/atlas_take_io/{codec,file}.*`独立维护 `.vslrun` schema1、UTF8与原子保存。宿主 `experiments/atlas_monitor_v1/takes.*`管理对话框／自动保护，`audio.*`管理live／record／replay。35项回归、实际静音设备自包含回放和2／12通道源一致通过；新UI交互／目视待检查。模块总图见[驾驶行程录制V1](../research/驾驶行程录制V1.md)，旧take协议不变。

最新低频接口：`modules/harmonic_body/{band,mix}.*` 配合 `dna_atlas::sa_voice_tick_body`，从同一谐波样本取出LF，再互补分配到DNA／机体包络；没有第二个时钟或随机源。`AdMix.body_mix`默认0，`AdCapture.body_raw/body/body_objects`分别保留原始L/R、混音后LF及机体代理；与独立高频残差一起只做一次空间渲染。`--body-mix`与原生“低频分层”旋钮已接入；34项回归、17条旧音轨一致及短时实际静音设备／UI检查通过。完整物理LF／NVH／工况模型及新音色听评仍缺，见[模块图与边界](../research/驾驶低频分层V1.md)。

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
