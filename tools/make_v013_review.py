"""Driving-listening page for passive engine/clutch coupling."""
import json
from runtime_review import ROOT
from comparison_page import comparison_page
OUT=ROOT/'renders/v0.13.0'
r=json.loads((OUT/'verification.json').read_text())
labels={'drive':'运动自动挡 · 30 秒驾驶','downshift':'制动与连续降挡','shifts':'手动换挡与关闭点火','neutral':'空挡补油与落转'}
cases={name:dict(label=label,
    takes={tag:'../renders/v0.13.0/'+r['cases'][name][tag]['audition']['file'] for tag in ['v012','v013']},
    gain_note=f'本组新旧共同固定增益 {r["cases"][name]["v013"]["audition"]["gain_db"]:+.2f} dB。相同踏板编排；RPM／负载不同。未分别归一化、压缩或降噪。')
    for name,label in labels.items()}
extra='''<p>优先比较起步、升挡衔接和制动降挡，再听空挡松油后的落转。新版用扭矩、曲轴惯量与离合摩擦联立计算转速；声源参数沿用上一版。</p>
<p class="quiet">车辆与离合仍使用工程参数。空挡落转的快慢尚待参考素材标定；能量预算闭合不代表声浪或驾驶性能已经像实车。相同 RPM／负载的四组台架音频与 V0.12 逐字节相同。</p>
<details><summary>查看实际驾驶与能量损失</summary><img src="../renders/v0.13.0/coupled_driving.png" alt="新旧转速、车速、挡位和新版轴端／离合扭矩与累计损失"><p class="quiet">模型输出，非实车遥测。离合摩擦热、传动损失和隐式求解的数值阻尼分别记录；累计账目只覆盖 RUNNING 控制步。</p></details>'''
page=comparison_page(title='V0.13 · 曲轴与离合耦合',version='0.13.0',headline='让转速由扭矩与离合共同产生',
    intro='<p>相同踏板输入，比较 V0.12 与 V0.13。保持松油保挡、制动安全降挡，以及各工况独立的声音层。</p>',
    cases=cases,methods={'v012':'V0.12 · 转速跟随','v013':'V0.13 · 离合耦合'},extra=extra,
    footer='<p><a href="V013曲轴与离合耦合.md">实现与验证边界</a> · <a href="V012试听.html">V0.12 对照</a> · <a href="V011试听.html">V0.11 音色对照</a></p><p class="quiet">实时工具：E:\\VehicleSoundLab\\Launch.cmd。选择 Pedal driving，Start 后使用 W／S 和 Q／E。</p>')
(ROOT/'research/V013试听.html').write_text(page,encoding='utf-8')
print('Written V013 four-pair driving review.')
