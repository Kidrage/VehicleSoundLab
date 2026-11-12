# 接火低频独立对照

复用`atlas_drive`、唯一`VslDrive`、A趋稳DNA、启动前段及stereo声床；仅新增CATCH低频附加层。不修改实时主链、UI、默认模型或`.vslrun`身份。

```powershell
cmake -S experiments/catch_bloom_v1 -B build-catch-bloom-v1 -A x64
cmake --build build-catch-bloom-v1 --config Release --target catch_bloom_probe catch_bloom_checks --parallel 4
ctest --test-dir build-catch-bloom-v1 -C Release -R '^catch_bloom_contracts$' --output-on-failure
```

`catch_bloom_probe MODEL START_PROFILE BLOOM_PROFILE OUT_PREFIX AMOUNT CHANNELS`，AMOUNT为0–1，CHANNELS为2或12。需要尚不存在的输出前缀。保存mix／base／raw／dna／startup／bloom及200Hz生命周期CSV；两次启动覆盖六生命周期。`bloom`是主增益前独立附加量，mix仅向FL/FR加入一次`0.25*bloom`。

`checks.c`用解析beta／指数、复数频率响应及长冲激衰减验证DSP，另检查mono、量0状态连续、1／240分块、同址处理、非法控制和事务读取。不是所有实时系统测试的替代。

完整复现脚本及保留失败见[研究记录](../../research/接火低频建立V1.md)。CATCH时长／RPM曲线沿用工程策略，不能把两次启停称为原视频同步复刻。
