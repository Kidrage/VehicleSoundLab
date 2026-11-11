# D/E素材接收与有限用途

用户2026-11-10批准D+E的音视频下载。原编码流已保存到工作区 `references/raw/`，未上传；双声道float32主文件在 `references/clean/`，完整来源、工具命令与SHA256保留。C仍未获批准，也未下载。

| 素材 | 已核对的画面／数据 | 当前用途 |
|---|---|---|
| D：REPerformance UK台架 | 1080p30，约59.536s，固定后左机位、封闭MAHA台架室；右侧屏幕可见变化读数。27.994s上右读数暂录为7093，但标签／单位未最终辨清 | 台架及过渡情境；不作为已验证的ECU RPM，不把室内频谱直接拟合为室外尾排 |
| E：AutoTopNL | 1080p60，约123.739s；包含室外镜头和多段车内仪表，Corsa与Sport布局不同。离散画面有可读挡位；图形转速表可以在另行刻度校准后估读 | 分段的挡位／驾驶情境与后续音画过渡观察；不直接拟合车外EQ |

E的82/84/86/88/90/94s画面分别显示1/2/3/4/5/6挡；这些离散点没有证明其间未剪辑，也没有给出精确换挡／断油时刻。仪表左下方的650/460/540 **km为续航**，不是RPM。66s仪表189km/h，而手机图层172km/h；不能把拼接手机读数当成同步ECU遥测。视频与音频的文件PTS只能提供时间坐标，没有独立测定显示延时或A/V误差。

原始解码没有增益、EQ、降噪、压缩或合并声道。D的L/R峰值约0.894/0.924；E约0.895/1.023，E右声道有7个样本超过1.0，float主文件完整保留。这个事实不足以证明话筒／ADC发生削波。现有检查没有主观听音，不能由统计量声称无配乐、无旁白、无AGC或来源分离清晰。

四个观察片段经 `tools/reference_segments.py` 校验raw／float哈希和双声道格式后登记在 `references/segments_v1.json`。允许用途明确限制为情境或动态观察，尚未开放RPM／阶次标定。

试听切片保留双声道，固定−6.0206dB及5ms端点淡化，不作去噪或高通：

- [D：20–32秒台架情境](../references/analysis/DE_observations_v1/D_dyno_gears_context.wav)
- [E：47–55秒Corsa仪表](../references/analysis/DE_observations_v1/E_corsa_first_context.wav)
- [E：58–77秒Sport仪表](../references/analysis/DE_observations_v1/E_sport_context.wav)
- [E：82–100秒第二段Corsa仪表](../references/analysis/DE_observations_v1/E_corsa_second_context.wav)

原始hash和声道统计：`references/analysis/DE_usability_v1/ingest.json`；逐帧PTS索引在该目录D/E子目录。密集补充画面及映射在 `DE_details_v1`；受限观察、切片处理与登记前后目录副本在 `DE_observations_v1`。这些材料可以继续支撑状态观察，但不能识别实车踏板／扭矩负载、燃烧持续时间或独立机体传递函数。
