# 固定怠速细谱适配层

`profile`组合只读Ms主声线、Mt幅度统计和Sf细谱参数；不含车辆名、RPM推断或第二套驾驶状态机。

`fi_state_create/destroy`在非实时线程编译卷积核、分配历史并预热；调用者须先销毁状态再释放借用的profile。`fi_state_tick`不分配、不读文件，持续推进全部OSC与随机激励；gate、主混合量、幅度起伏量和细谱量互相独立。

外层gate由唯一驾驶器提供。80ms立方淡化是实验宿主策略；混合量用18ms指数跟随，主声线起伏与细谱量用18ms有限斜坡。输出含受控主声线、细谱、两者原始和、外层包络后声音及旧声源保留量。房间、空间宽度、输出增益不在此层。

当前F2候选为固定源：13条独立频率OSC＋新生成的相关幅度变化＋6个8192tap细谱滤波器／新高斯激励。无PCM时间轴或录音循环，保留录音透视下的谱形；这不等于剥离了真实机体／排气／麦克风的物理贡献。真实RPM未知，集成时ratio固定1。

驱动器通过`AdConfig.fine_idle_profile`选择本层，与旧`idle_profile`和opaque源回调互斥。`AdMix.idle_mix/idle_motion/idle_detail`均为0..1；未配置此层时后两项必须为0。`AdCapture.idle_modal/idle_detail`位于外层gate与电平前，用于分轨和行程源哈希。

新增堆状态要求非实时调用`ad_render_dispose`／`am_render_dispose`／`at_player_dispose`，然后才能重新初始化或释放资产。只能对已零初始化或成功初始化的对象销毁，重复销毁安全。宿主在音频线程停止后统一执行。

数值验证、设备时序与听评分开；本层尚未获得新音色认可，也不代表完整怠速RPM／负载或多发动机标定完成。
