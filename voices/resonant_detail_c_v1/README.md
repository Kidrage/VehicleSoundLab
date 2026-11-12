# 连续共振细节参数

现有JSON参数的C可读导出，无重新拟合、PCM、录音轨迹或房间处理。原始模型、SHA、混合配方和适用状态见`index.json`。

| 参数 | 来源 | 使用范围 |
|---|---|---|
| `moving_35.rdetail` | `resonant_detail_v1/detail.json`的`replace_35` | 用户暂留的离线行驶配方；C核数值核对通过，完整C混音未验证 |
| `idle_add.rdetail` | `idle_resonant_v1/detail.json`的`add_only` | 低转补细节候选，待听评；未确认热怠速／RPM |
| `idle_35.rdetail` | 同模型的`replace35` | 低转轻量谐波替换候选，同上 |

文本按空白分隔：

```text
VSL_RESONANT_DETAIL 1 48000 频带数 预热帧数 声学根音Hz
每带：AR阶数 SOS节数 包络阶数
      下限Hz 上限Hz 激励sigma 细节增益 观察R/L比
      AR分母a[0..阶数]（a0为1）
      每个SOS的b0 b1 b2 a0 a1 a2（a0为1）
      全部cos系数，随后全部sin系数（包络阶数0则省略）
```

`.rdetail`只描述新增细节。主DNA的功率削减、1.2–1.9kHz过渡和低频保持由完整配方的调用者完成；当前没有该混合适配器。原`resonant_detail_v1/SELECTION.json`属于旧离线选择快照，历史`not_ported`字段不改写；当前C移植范围以此目录和新汇总为准。
