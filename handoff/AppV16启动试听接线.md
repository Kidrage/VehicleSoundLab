# App V16 启动试听接线

2026-11-17。入口仍为 `Launch-Vehicle-Sound.cmd`。默认V10驾驶页增加“新启动试听”和“旧 V3 对照”，每次7秒，0.81–1.91秒拖转不同，接火和后续DNA怠速一致。按钮使用固定配方，静音／停止可用；普通驾驶、参数和行程路径继续独立工作。此处是待听评启动候选，不表示用户已认可音色。

`AuditionHost`是同一App的一次有限试听会话；它创建现有主C引擎，按照240帧控制网格采用原试听生命周期，不新增车辆控制器。`modules/startup_character/scene.c`按同一个音频帧计算前置、拖转、接火的进度／音高、包络与交接权重，调用三组现有C声源；将前景与主引擎合听。声源和加权混音均在C，Python只准备参数、调用和投递声卡。无PCM、原片段循环、房间或空间渲染。

新拖转复用 `crank_rotation`；旧V3使用原移动OSC。共同预热、随机种子、旋钮及固定电平来自上轮冻结配方，新增C场景不是重新拟合。`sc_mix_scene`另可输出前置／拖转／接火／怠速四条立体声分轨，便于核查与后续对象化。试听不伪装成普通驾驶行程：界面拒绝将它保存为缺少前景身份的普通take。

参数在 `experiments/startup_character_v1/runtime_bank/`，含相对路径、SHA256清单、三组细谱滤波器和全部OSC／运动参数；合成谱色FIR不是原录音或房间IR。这里不放入全局voices身份域，避免破坏原有行程的声音参数身份。运行只依赖Python标准库、主v14库和独立v5启动库。

构建：`Build-Vehicle-Source.ps1`构建整车声源并调用`Build-Startup-Audition.ps1`；后者只构建启动库。`Build-Startup-Audition.ps1`对应`build-startup-character-v5`，v4冻结试听及v13旧行程库保持原字节。

验证工具为 `tools/verify_startup_audition_v1.py --output <新目录> --ui`。检查真实流式C与冻结新旧音频、217／480 API分块、四分轨重组、接火后完全一致、非法时序拒绝、两次7秒真实WinMM静音试听、中止及不能保存伪行程；检查按钮完整可见并截取本App窗口。初次verification1功能通过，但人工检查截图发现右栏旧版按钮受挤压，已把两个按钮移动到驾驶页主栏并加强祖先容器裁切检查；最终采用verification2。

此前开发状态已推送至GitHub分支`research/coherent-low-v1`，提交`f277e7c`。V16接线与参数库作为后续提交同步同一分支。主分支不自动合并。
