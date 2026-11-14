# 带限 DNA 加载实验

本目录验证较高根频率参数如何接入已有持续OSC／驾驶系统，不拟合新素材或改动默认声音。

```text
.model ─ sd_profile_load ─ sa_bank_init ──────┐ 旧接口与保护
       └ sd_profile_load_bandlimited         │
          └ sa_bank_init_bandlimited ────────┴─ SaVoice ─ 驾驶包络 ─ 独立空间化
                                               唯一现有OSC／统计纹理
```

两个新接口均在非实时线程调用。新接口允许`base_hz`为5–1000Hz，逐项校验全部分音系数；模型和bank由调用方拥有，保持只读并覆盖voice整个生命周期。旧`SdVoice`不能用于不满足旧保护的模型。

```c
const SdProfile *models[1] = { &profile };
if (!sd_profile_load_bandlimited(path, &profile)) return 0;
if (!sa_bank_init_bandlimited(&bank, models, 1, 0)) return 0;
if (!sa_voice_init(&voice, &bank, 23117, actual_root_hz, 1, 1)) return 0;
/* Audio thread: sa_voice_process(&voice, interleaved_double_stereo, frames). */
```

初始化时不裁剪模型阶数；播放时现有渲染器按实际根频率对每阶载波渐隐。该机制不能保证任意随机调制边带的严格带限。根频率是声学坐标，不是测得的曲轴RPM。

```powershell
cmake -S experiments/bandlimited_dna_v1 -B build-bandlimited-dna-v1 -G "Visual Studio 17 2022" -A x64
cmake --build build-bandlimited-dna-v1 --config Release --parallel 2
ctest --test-dir build-bandlimited-dna-v1 -C Release --output-on-failure
```

专项检查分为加载／失效事务、解析载波／双声道／扫频／分块、同驾驶器2／12通道三份C文件。`test_models.*`只生成已知测试参数。新离线宿主`probe.c`只解析参数、调用原SaVoice、写FLOAT WAV，不含自己的合成算法：

```text
sound_dna_bandlimited_export.exe model out.wav seconds root_hz detail seed block_frames
```

`root_hz`是绝对根频率0–1000，非旧导出器的0.9–1.1相对音高；输出为48kHz、unity双声道、无混响／监听淡入。seed显式且非零，块长1–512。`--describe`返回独立协议`vsl.sound-dna-bandlimited-export/1`。同目录的`sound_dna_legacy_export`仅将原raw宿主重新链接用于回归。

现有UI、目录和schema10 owned资源校验仍使用旧路径。直接高锚点驾驶测试通过不代表这些产品入口已经支持高锚点录放。旧播放器和行程须成对保留。
