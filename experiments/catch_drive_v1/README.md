# 接火层统一驾驶验证

复用 `atlas_drive`、同一 `VslDrive`、A趋稳DNA与启动纹理。没有新增声源内核或驾驶控制器。

| 文件／目标 | 职责 |
|---|---|
| `checks.c` / `VslCatchDrive_checks` | 独立量、两次启停、旁路、分块、单次路由、解析混合／独立声部对照、控制事务 |
| `probe.c` / `VslCatchDrive_probe` | 统一链实际导出mix、raw、DNA、启动、接火附加量与驾驶CSV |

在工程根目录构建：

```powershell
cmake -S handoff -B build-catch-drive-v1 -A x64
cmake --build build-catch-drive-v1 --config Release --parallel 4
ctest --test-dir build-catch-drive-v1 -C Release --output-on-failure
```

探针参数：`VslCatchDrive_probe A_cabin.model early.start bloom.cb OUT_PREFIX amount0..1 channels2|12`。输出两次启停、六生命周期，共6秒。输出路径已存在则拒绝。

原生入口 `Launch-Catch-Study.cmd`，默认停止、接火量0%。新`.vslrun`为schema5／27字段，须用匹配播放器；旧schema4播放器保存在本阶段`before/bin`。

45项系统测试及短设备／行程检查已通过，完整音色、人耳、长时间及实际12扬声器未验收。证据、运行说明和模块图见[接火低频统一驾驶V1](../../research/接火低频统一驾驶V1.md)。
