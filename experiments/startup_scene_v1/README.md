# 同录音启动衔接探针

只有宿主和文件导出；声音来自已有`atlas_drive`、`dna_atlas`、`start_texture`，驾驶状态仍由唯一`VslDrive`决定。该目录未引入第二个合成器或新实时库。

`startup_scene_probe A_cabin.model early.start OUT_PREFIX startup0..1 channels2|12`生成6秒、两次完整启停，以及raw／DNA／启动层分轨和控制CSV。根音／既有怠速的比值仅为预览映射，无法当作ECU标定。启停曲线是原工程策略，快速接火／低频建立尚未按实录拟合。

构建：`cmake -S experiments/startup_scene_v1 -B build-startup-scene-v1 -A x64`，再`cmake --build build-startup-scene-v1 --config Release --target startup_scene_probe`。依赖现有handoff目标，不改原宿主或录制身份。

模型编译／源身份、四组渲染、两布局前置一致和非重复混音检查见[研究记录](../../research/启动后车内DNAV1.md)。试听、设备和长期验收分别记录，不把离线通过当作全状态还原。
