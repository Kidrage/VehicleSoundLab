# 连续共振 C 验证宿主

`VslResonantDetail_probe profile.rdetail output.f64 frames seed starting_phase_cycles`按固定声学根音推进相位，输出小端double行：L、R、逐带单位增益信号。不是WAV、完整混音或驾驶轨迹。文件打开与写入只在此离线宿主；模型不合法时先拒绝，不创建输出。

`VslResonantDetail_checks moving_35.rdetail idle_add.rdetail`检查解析阻尼冲激、极点／包络范围、同seed重置、左右关系、非法相位不改状态和事务加载。

契约还在同一翻译单元包含`residual_dense/voice.h`并链接其旧实现，验证旧`Rd/rd_`与新`Rdt/rdt_`公开接口可共存。

从`handoff`CMake构建。完整验证入口`tools/verify_resonant_detail_c_v1.py`另检查三参数×三seed，C输出与原Python生成器同序列比较。详见[阶段记录](../../research/连续共振细节C核V1.md)。无新原生窗口、默认音色或驾驶字段。
