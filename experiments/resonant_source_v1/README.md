# 完整共振声源配方验证

离线探针：

```text
VslResonantSource_probe 原DNA.model LF.model或- detail.rdetail或- 输出.f64 功率替换量 细节seed 帧数 通道数 相对音高
```

原DNA／LF的统计seed为既有48271，LF校准为既有1.6658265329883064，主增益0.5、宽度1。仅离线宿主使用固定测试配方；库控制另有独立接口。

每行小端double：输出2或12通道，DNAraw L/R、LFraw L/R、校准LF L/R、细节 L/R、未乘主增益mix L/R、主声相位。因此每行13或23列。没有WAV解码或原片播放路径。

`VslResonantSource_checks`覆盖已知功率mask、低阶／相关参数保持、非法模型／控制不改状态、无细节时旧源一致、静音内部状态不冻结、变调时相位共用、主DNA包络同时门控细节及2／12路由。探针和契约均由`handoff`构建。

`tools/verify_resonant_source_v1.py`把三个配方×三个seed的实际C输出与冻结离线混音／分轨逐样本比较；各8秒。没有重新拟合或逐条增益补偿。C／Python细节核精度与整个混音的float文件舍入误差分别报告。详见[阶段说明](../../research/完整共振声源C接入V1.md)。
