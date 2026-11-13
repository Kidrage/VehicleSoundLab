# 独立声线幅度纹理

本模块给独立 OSC 声线添加新生成的相关幅度变化。当前 F2 怠速参数来自录音的短窗幅度统计；它是待听评的声学代理，不代表物理燃烧分离或已知 RPM。这里没有车型分支、录音循环、频率／相位调制或房间处理。

```text
不可变协方差因子 → 新高斯向量 AR → 方差归一插值 → 正幅度增益
                                                         ↓
不可变独立声线参数 → 原 modal_source OSC → 左右共用逐声线增益 → Stereo
```

| 文件 | 职责 |
|---|---|
| `profile.*` | 48kHz、最多64声线、更新间隔／相关系数／因子的非实时校验 |
| `envelope.*` | 独立随机状态、相关幅度生成、18ms量平滑；0量仍推进 |
| `voice.*` | 组合现有OSC与幅度核，提供`mt_voice_init/set/tick/process` |
| `io.*` | 严格版本化`.mtexture`读取，独立链接；失败不修改输出 |

模型用因子`F`表示协方差`C=F·Fᵀ`，允许奇异／全零。每次更新`z_next=alpha*z+sqrt(1-alpha²)*F*n`；相邻向量作余弦插值，并除以实际插值标准差。量`s`下的增益为`exp(s*z-s²*Cii)`，在高斯边际模型内保持期望增益平方为1；有限片段电平仍会变化。

同一声线的L/R乘同一增益；频率、初始相位、抗混叠与OSC推进仍由`modal_source`负责。`ms_voice_tick_gains(NULL)`保留原算术；0量走此旁路。ratio只改变独立声线频率，不等于发动机RPM或完整滤波器变调。

两个profile都由调用者拥有，初始化后只读并须比voice存活更久。初始化／文件读取在音频线程外执行；set/tick/process仅用预分配状态，不分配内存或做IO。输出不能与状态／profile重叠。量控制0–1，反复设置同一目标不会重启18ms过渡。

实验构建：`cmake -S experiments/modal_texture_v1 -B build-modal-texture-v1 -A x64`，然后常规Release构建及CTest。`tools/verify_modal_texture_c_v1.py`导出冻结参数并核查C/Python；`probe`可生成不依赖Python的持续主声线WAV。

此模块尚未接入驾驶器／原生UI／行程格式，也未替换认可音色。8192点细谱FIR仍在Python；把C主声线与原Python细节混音只用于移植对照，不能称完整C移植或实时成本通过。旧严格行程继续配套冻结播放器。
