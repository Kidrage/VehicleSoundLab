# 连续共振细节 C 核 V1

2026-11-12。已将既有离线连续细节生成器移为独立C模块，并验证三个参数的数值一致性。**仅完成细节核；未完成完整DNA＋低频＋细节混音、原生监听或驾驶接入。** 行驶音色继续暂留离线V1的35%，不做新调音。低转两个候选仍待原听评问题，不据技术测试判定音色完成。

## 模块与控制边界

`modules/resonant_detail`分为参数验证、连续随机激励、AR／SOS滤波、能量包络、声部五部分；`modules/resonant_detail_io`独立非实时加载。参数为`voices/resonant_detail_c_v1`的行驶35%、低转add／35%；均从冻结JSON直接导出，未重新拟合。

信号为：独立每带高斯激励→素材AR共振→外部相位下的弱能量包络→固定Hz带通→各带增益／观察R/L比。没有录音循环、PCM轨迹、房间或新事件触发器；属于Sound DNA纹理，不等于物理噪音分离，也不是严格纯OSC。低转所有周期包络仍为平坦。

`rdt_voice_tick`不分配、不I/O、不自建发动机时钟。调用者持有只读模型，并传入`[0,1)`主声相位；初始化、稳定性／正值验证和加载在非音频线程。当前48kHz，12带／AR24／4SOS／12阶包络上限；Schur极点半径小于.9998，网格加导数界验证连续相位功率至少.05。见[模块接口](../modules/resonant_detail/README.md)。

交接复核发现初版`RdVoice/rd_voice_init`与旧`residual_dense`同名，单独探针没有暴露。新模块统一改为`Rdt* / rdt_* / RDT_*`，旧接口不动；同一契约包含并链接两套库。该修正未改参数或算法，后续以重新构建／测试后的`verify4`为准。

`.rdetail`仅生成细节，**不自行执行35%谐波功率替换**；主DNA过渡／削减和原相干LF必须由后续适配器处理。固定共振器Hz尚无全RPM×负载映射；改相位不能自动获得带载音色。`base_hz`是声学坐标，不是实车RPM。观察左右比不表示物理缸列或空间定位。

## 实际验证

| 检查 | 结果 |
|---|---|
| 独立构建及全部CTest | 48／48通过，含原47项及新共振契约 |
| 原C/H | 478份字节不变；新增14份，共492份，索引已更新 |
| C／Python比较 | 3参数×3种子；每次4秒，含2秒预热，比较后2秒 |
| 最大逐带绝对差 | 行驶3.11e−14；低转样本相等 |
| 最大细节立体声绝对差 | 5.49e−16 FS以内 |
| 非法模型 | 5例拒绝，未先创建输出；事务输出保持契约通过 |

种子8121907／23117／61927，保留原xorshift64*／Box–Muller顺序，AR／SOS按原SciPy运算顺序，MSVC使用`/fp:strict`。解析阻尼冲激及正值／极点反例独立于实际模型比较。以上证明细节算法移植，**不证明完整混音听感或实时设备资格**；离线探针含初始化和文件I/O的速度不作为回调预算。

原先`verify1`已构建并通过48项，但验证脚本误以为CTest必须打印“0 tests failed”而中断。`verify2`修正摘要匹配，复用字节未变的构建／测试日志，再完成9组实际比较。`interface_review1`留痕接口冲突；`verify3`新共存契约因handoff未声明旧库目标而链接失败，补入原库构建后由`verify4`重新构建、运行48项和9组比较。失败及各次执行源码均保留；原离线选择文件／历史冻结摘要不改写。

`final2`发现验证脚本在CMake自动重配置前记录缓存SHA，测试后校验不一致；未更新索引／摘要。改成绑定构建后的缓存；`verify5`复用完整报告时又把预期返回2的非法输入检查当作构建失败，修正为仅对构建／CTest要求返回0。`verify6`复用未变C源码及`verify4`通过的构建／CTest日志，重做9组细节比较和非法输入检查；`final3`发布当前索引／汇总。这些为证据工具修正，无新DSP／参数变化，不重复已通过的C测试。

## 复现与交接

独立研究构建`E:/VehicleSoundLab-Git/build-resonant-detail-c-v1`，旧宿主／播放器保持。仓库`Build-System.ps1`下次完整构建也会包含新契约。

```powershell
cmake -S handoff -B build-resonant-detail-c-v1 -G "Visual Studio 17 2022" -A x64
python tools/verify_resonant_detail_c_v1.py --workspace E:/VehicleSoundLab --build E:/VehicleSoundLab-Git/build-resonant-detail-c-v1 --out E:/VehicleSoundLab/references/analysis/resonant_detail_c_v1/verify-new
```

`python`指安装了本项目分析依赖的解释器；输出目录须不存在。摘要[resonant_detail_c_v1_summary.json](resonant_detail_c_v1_summary.json)。证据`E:/VehicleSoundLab/references/analysis/resonant_detail_c_v1/{export1,verify1,verify2,final1,interface_review1,verify3,verify4,final2,verify5,verify6,final3}`；与本轮Sport素材检查一并冻结于`E:/VehicleSoundLab/baselines/resonant_detail_c_v1`。

下一步先做可选完整混音适配器，逐样本验证DNA替换／低频／细节的组合，再接同一驾驶相位、监听和行程。低转候选等待已有反馈；状态及负载参数不足继续按独立素材补证，不能把行驶配方直接全音域拉伸。完整怠速／带载加速、设备长时、跨发动机及实际7.1.4仍未完成。
