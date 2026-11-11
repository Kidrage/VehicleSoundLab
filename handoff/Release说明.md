# Vehicle Sound Lab · 完整工程交接

本次 Release 提供可运行系统、全部冻结版本、已批准的 A/B/D/E 原始素材与清洗文件、分析数据、试听、驾驶录制及分轨渲染。

- 原始八份 ZIP 共约 19.39 GB。大于 GitHub 单附件上限的文件按字节分为 .part01、.part02，原始 ZIP 的内容和 SHA-256 保持不变。
- 下载所有附件后执行 python Restore-Release.py .，校验并合并为八份原始 ZIP。
- 再执行 python Restore-Handoff.py E:\VSL-Work .\01-system.zip .\02-history.zip .\03-references.zip，按需追加渲染和分析依赖包。恢复到新建的空工程目录。
- 从恢复后的目录双击 Launch-System.cmd；源码构建和 C 模块图见仓库 README。
- release-manifest.json 记录每个分包和原始 ZIP 的 SHA-256；package-index.json 记录 48 个冻结版本与原始交付验证。

驾驶功能主线、固定情境获认可的 Sound DNA，以及未通过听评的低频 V2 分别保留。完整素材的来源和已批准用途随证据包附带。
