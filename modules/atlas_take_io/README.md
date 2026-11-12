# 行程文件 I/O

非实时模块。`at_take_encode/decode` 处理内存，`at_take_save/load` 处理 UTF8 路径。当前独立 `.vslrun` schema3，25控制字段，配置新增对象／立体声声床模式；旧 `.vsltake` schema5保持原协议。schema2使用`baselines/system_status_v1`或`stereo_bed_v1/before/bin`匹配播放器，schema1使用`baselines/atlas_take_v1`。本版本明确拒绝旧格式／旧渲染身份。

文件顺序：8字节 `VSLRUN\r\n` → u32版本 → 64字节渲染身份 → u32控制字段数 → 配置／DNA／对齐后的相位、单位复数、差分、正弦表／可选残差 → 初始化控制 → 帧数、停止帧、双哈希 → 控制事件 → u64 FNV校验。整数与IEEE754双精度均显式小端，不dump C结构体。

最大32MiB；锚点、谐波、统计组件、残差频带、事件数量及所有控制均有上限和范围验证。截断、尾随、错误版本／身份／校验及非法模型事务拒绝，原行程不变。成功载入拥有全部模型，不依赖外部路径。保存通过同目录独占临时文件、flush和原子替换；普通I/O失败保留既有文件。
