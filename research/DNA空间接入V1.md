# DNA／低频空间接入 V1

2026-11-11。前一轮相干低频获得用户反馈“实测相位更像发动机，厚度也改善”。认可模型与种子、增益另存于 `coherent_low_v1_acceptance.json`；原冻结实验保留，不回写当时的pending状态。

本轮新增 `modules/dna_scene`：两条持续OSC源 → 明确观察投影／出口路由 → 十源接口 → 现有立体声／7.1.4渲染。源、路由和空间适配器分别维护，没有把算法链放进一个文件，也没有运行驾驶旧DNA。共用代码还渲染了Warm/Hollow合成测试模型，验证其他谱形可使用同一路径；这不是新增实车还原验收。

## 生成与验证

- 新DNA与实测相位低频原始float输出，分别与上一轮冻结生成结果逐样本一致；低频校准倍率为1.6658265329883064，输出增益统一0.5。
- 两层独立种子均显式保留48271；静音不会停时钟，0.90–1.10×音高控制保持两层声学相位时钟一致。其他种子下的跨层统计关系尚未听评。
- 空间／透视／传播和2／12通道变化不改变原始源、直送监听或空间前分轨。分块方式、无效参数拒绝、低频可空、出口投影也有C验证。
- 该观察片段近乎双单声道，默认取左观察，分半幅度给两个出口；没有从录音中分离左右缸组。无房间的对称投影仍为对称输出；单侧出口互换后左右输出镜像。
- 无房间的12通道高度四路严格静音；有房间时仅接收反射。检查了WAVE speaker mask与通道数、帧数。九组渲染均未削波；最高峰值约0.396。
- 独立C接口测试通过。统一构建新增同项验证，在原25项之外增加1项。空间听感仍待用户确认，技术验证不能替代听评。
- 统一26项CTest全部通过。试听页八条音频载入、单播放器与窄屏布局检查通过，浏览器QA全程静音；直送试听与原认可混音最大差异为一个PCM24量化步长。

空间层有28Hz高通、120Hz分频、距离和合成早反射，输出电平也随投影改变。试听不做逐条响度匹配或增亮，先用直送监听确认已认可的组合，再比较无房间／房间／几何传播。物理上相干源产生的相消不能通过给观察声道失谐来掩盖。

## 复现

```powershell
cmake -S experiments/dna_scene_v1 -B build-dna-scene-v1 -G "Visual Studio 17 2022" -A x64
cmake --build build-dna-scene-v1 --config Release --target dna_scene_probe dna_scene_checks --parallel
ctest --test-dir build-dna-scene-v1 -C Release -R "^dna_scene_contract$" --output-on-failure
python tools/run_dna_scene_v1.py --workspace E:/VehicleSoundLab --probe E:/VehicleSoundLab-Git/build-dna-scene-v1/Release/dna_scene_probe.exe
```

输出目录必须不存在，防止覆盖。生成 `E:/VehicleSoundLab/references/analysis/dna_scene_v1/` 的原始C渲染、分轨、试听和JSON报告，以及[本机试听页](http://127.0.0.1:8789/research/DNA空间接入V1.html)。页面仅播放立体声，12通道保留为独立WAV。原始浮点文件无起止淡化；试听PCM24只加5ms文件边缘淡化。分析脚本只调度、校验和包装C输出，不代替C合成。

源码提交且工作区干净后，`python tools/freeze_dna_scene_v1.py --workspace E:/VehicleSoundLab` 将本轮证据、可执行文件、测试日志、源码ZIP和便携试听冻结到独立 `baselines/dna_scene_v1/`。冻结前核对渲染所用源码与二进制指纹，之后逐文件SHA-256校验；已有目录会拒绝覆盖。

## 当前边界与下一步

这是已认可声源接空间的第一条可复现链，不修改旧驾驶DSP0.20.0／take schema5，不改变现有监听窗口默认声音，也不修改冻结Release。新研究需要本轮源码和本地增量证据。

尚未完成：新组合的空间听评与设备监听、其他实车／宽RPM／负载模型库、跨模型连续过渡、与统一驾驶控制器接入、进气及回火等声源的逐层听评。完整驾驶仍用旧主线，不能将本次接口验证称作整车声浪完成。
