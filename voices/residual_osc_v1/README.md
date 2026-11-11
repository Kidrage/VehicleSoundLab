# 残差声层实验模型

`A_exterior.residual` 与 `E_cabin.residual` 分别来自 A 驻车车外 Upper Mid 和 E 高转车内 Lower 的冻结观察。二者使用相同的 `sound_residual` C11生成器，保留各自频带功率与左右复相关。

模型仅用于固定锚点离线对照，音色尚未通过听评。没有添加到驾驶默认列表，也不能与已认可的 A 移动尾排相干低频直接组合为同一录音情境。来源与哈希见[研究摘要](../../research/residual_osc_v1_summary.json)；导出方法见[模块说明](../../modules/sound_residual/README.md)。
