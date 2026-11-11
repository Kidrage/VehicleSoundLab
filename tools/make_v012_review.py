"""Simple driving-response review; preserve historical listening pages."""
import json
from runtime_review import ROOT
from comparison_page import comparison_page
OUT=ROOT/'renders/v0.12.0'
r=json.loads((OUT/'verification.json').read_text())
labels={'drive':'运动自动挡 · 30 秒驾驶','downshift':'制动与连续降挡','shifts':'手动换挡与关闭点火','neutral':'空挡补油'}
cases={name:dict(label=label,
    takes={tag:'../renders/v0.12.0/'+r['cases'][name][tag]['audition']['file'] for tag in ['v011','v012']},
    gain_note=f'本组新旧共用固定增益 {r["cases"][name]["v012"]["audition"]["gain_db"]:+.2f} dB。相同踏板编排；RPM／负载会不同。未分别归一化、压缩或降噪。')
    for name,label in labels.items()}
extra='''<p>先听自动挡中的加速、松油保挡和制动降挡，再比较手动换挡。音色参数沿用 V0.11；本轮主要改变驾驶过程中转速、负载和各层的响应。</p>
<p class="quiet">当前车辆动力学仍含工程假设。两个厂家峰值参数不足以确定整车动力曲线；数值测试不代表真实度认可。相同 RPM／负载的四组台架导出与 V0.11 逐字节相同。</p>
<details><summary>查看驾驶与轮上力曲线</summary><img src="../renders/v0.12.0/driving_forces.png" alt="新旧 RPM、车速、挡位与新版本的轮上力、阻力和负载曲线"><p class="quiet">这些曲线由本地模型产生，不是视频遥测或测功机记录。开启本地界面的 Pedal driving 可直接操作。</p></details>'''
page=comparison_page(title='V0.12 · 纵向动力链',version='0.12.0',headline='让挡位、扭矩与阻力共同决定驾驶响应',
    intro='<p>相同踏板输入，比较 V0.11 与 V0.12。继续保留松油保挡、制动安全降挡和分层声音状态。</p>',
    cases=cases,methods={'v011':'V0.11 · 原驾驶模型','v012':'V0.12 · 轮上力模型'},extra=extra,
    footer='<p><a href="V012纵向动力链.md">实现与参数依据</a> · <a href="V011试听.html">V0.11 音色对照</a></p><p class="quiet">实时界面：E:\\VehicleSoundLab\\Launch.cmd。启动保持静音；选择 Pedal driving，Start 后用 W／S 和 Q／E 操作。</p>')
(ROOT/'research/V012试听.html').write_text(page,encoding='utf-8')
print('Written V012 driving review: four common-gain pairs.')
