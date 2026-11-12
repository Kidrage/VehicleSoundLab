# 连续共振参数 I/O

与`resonant_detail`实时核分开链接。`rdt_profile_read(FILE*, RdtProfile*)`读取有界文本并完整校验后提交；失败时保留输出模型。`rdt_profile_load(UTF8路径, RdtProfile*)`使用既有`vsl_fopen`，仅允许在非音频线程调用。

文件格式见[参数目录](../../voices/resonant_detail_c_v1/README.md)。加载不启动声部、不预热、不改驾驶器；模型生存期、运行时只读和新旧声部切换由宿主管理。本版本没有UI、行程或默认模型接入。
