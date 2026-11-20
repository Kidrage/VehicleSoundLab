# ADSP-21569板测入口与验收

2026-11-20 补充：本次内存优化必须另外启用 `VSL_FIXED_V10` 并加入 `embedded/fixed_assets.c`。完整步骤见 [内存版接入](内存版_板端接入.md)；本页旧 production 配置不会自动切换 compact。用户后来补充的前版峰值为 1174.11 MCPS，本次内存版尚未重新板测。

本包尚未进行CCES编译、链接或ADSP上板测量。PC耗时不能换算成ADI MCPS；1882.91 MCPS是用户提供的原版本峰值。500MCPS以内需要原峰值下降至少73.45%，当前不能据PC结果宣布达标。

1. 沿用48kHz、256frame、float、CCES2.12.1/compiler8.16.1.0、-double-size-32及原Release参数。开启VSL_ADSP_21569、VSL_DSP_STATIC、VSL_DSP_APPROX、VSL_DSP_FIR_TAPS=512、VSL_DSP_FAST_TRIG；强制包含modules/dsp_support/fast_math.h。新表默认VSL_DNA_TABLE_HOP=128；旧VSL_DSP_WT_HOP=32不能覆盖这一默认，应删除旧宏或设置成相同128。
2. 按根sources.cmake选取编译单元；dsp/文件替换对应旧模块C文件，勿同时编译两个同名实现。加入dsp/perf.c、dsp/diagnostics.c，生产版关闭VSL_PROFILE与VSL_CAPTURE_MODULES。PC桥接器和tools/render_cases.c不属于板上音频入口。所有内部结构必须重编译。include根为工程根、modules、src、generated、modules/sound_dna、voices/events_v1。
3. 同步替换.sfir资产和modules/startup_flare/model.c，若板上另有资产固化工具，必须从新参数重新生成。不能继续加载旧8192参数或在外层再次做512窗口裁剪。本次短FIR API只接受最多512阶。此ZIP没有用户CCES工程、板卡下载器或完整板上资产桥接工程，需集成进现有工程。
4. 核对ADI库cfft128/ifft128/ifft2048的原型、对齐、缩放与返回缓冲规则。本地MSVC走便携FFT分支，不能替代对ADI分支的验证。SaTable按8字节对齐放seg_vsl_l2_history，主体112904B为PC ABI实测；其中绝大多数为float数组。短FIR频谱+历史池101376B放seg_vsl_l1_fir，原512窗口版对应99072B；原每FIR8192样本延迟池共393216B被移除。SaSampleCache维持单锚点，RDT运行时维持小结构和原全局包络LUT。以上是部分池，不是全工程RAM；必须检查实际LDF/map、L1分区/cache配置和栈峰值。

无插桩总耗时为达标依据：在原测量外壳中计时控制参数接收和vs_engine_process，排除初始化、I/O、打印、JTAG和空间渲染。生产必须保留声音输出，不要用静音替代未使用的实际声源。

```text
MCPS = block_cycles * 48000 / frames / 1e6
256frame时500MCPS对应2,666,666 cycles/block
```

模块定位另开VSL_PROFILE并编译dsp/perf.c，在现有板工程中实现`uint64_t vsl_board_cycle_count(void)`，返回原有可靠周期计数器的64位单调结果（正确处理回绕、编译器屏障）。在稳态/启动测量窗口前调用vsl_perf_clear，窗口后读取vsl_perf_get。结构包含exclusive、inclusive、calls，模块ID见docs/module_names.json；exclusive避免嵌套重复，inclusive只用于查看父链含子项的总成本。计时插桩有开销，另测空计数对；不能把开启逐样本插桩的总MCPS作为500门槛依据，禁止在音频循环里打印。模块计数窗口按实际总frame数换算MCPS，整体峰值要由无插桩的每块cycles统计。

必须覆盖：启动前景/背景叠加、怠速、0→8000RPM加速、8500RPM高转、5625RPM四路事件叠加、快速穿过5062.5–6187.5RPM的共振支持区、离开后重新进入、松油门、制动、换挡、熄火、取消启动与连续重启；再测air=0以及播放中改air/line。记录平均、P99、最大值、块相位，至少统计所有128采样波表更新与64采样FIR更新的组合。还需确认无欠载、NaN、堆分配和持续堆栈增长。

如500MCPS未达标，先用新模块数据决定是活动共振滤波还是波表/启动/事件突发占主导。可对照VSL_DNA_TABLE_HOP=64听评更细调制；进一步减少模态/滤波阶数需要另做谱与听感验证，当前保留这些阶数。
