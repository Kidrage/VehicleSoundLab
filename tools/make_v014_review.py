"""One optional listener model, using identical source objects and driver state."""
import json
from runtime_review import ROOT
from comparison_page import comparison_page

r = json.loads((ROOT/'renders/v0.14.0/verification.json').read_text())
labels = {'idle':'1200 RPM · 直达声', 'mid':'4000 RPM · 直达声',
    'high':'8000 RPM · 直达声', 'drive':'运动自动挡 · 含原有空间反射',
    'cabin':'车内视点 · 工程预览', 'imported':'导入合成器 DNA · 直达声'}
cases = {name:dict(label=label,
    takes={tag:'../renders/v0.14.0/'+r['cases'][name][tag]['audition']['file'] for tag in ['legacy','propagation']},
    gain_note=f'本组共同固定增益 {r["cases"][name]["propagation"]["audition"]["gain_db"]:+.2f} dB。没有分别归一化。距离衰减、相位和频谱差异保留；驾驶状态与源波形相同。')
    for name,label in labels.items()}
extra = '''<p>建议先用耳机比较 1200／4000／8000 RPM：关注两侧空间位置、高频是否变薄、合成器嗡鸣是否仍明显。扬声器播放会另外产生双耳串音；7.1.4 导出采用监听中心路径，不套双耳滤波。</p>
<p class="quiet">这次只增加可旁路的直达声传播。1.4 m 参考距离、18 cm 耳间距及简化头部遮挡均为工程配置；不是实测 HRTF、排气 IR 或实车空间标定。原来的早期反射保持独立，主音色尚未获得主观验收。</p>
<details><summary>查看传播滤波器的高频误差</summary><img src="../renders/v0.14.0/fractional_path_response.png" alt="编译后的C传播模块在17种分数延迟下的幅度和相位误差"><p class="quiet">这里只比较分数延迟与理想延迟；故意加入的远耳头部遮挡另行计算，不包括在这张误差图中。13 个采样的共同算法延迟单独记录。</p></details>'''
page = comparison_page(title='V0.14 · 直达声传播', version='0.14.0',
    headline='同一组声源，比较到达左右耳的路径',
    intro='<p>发动机 DNA、机械、气流、事件和驾驶模型保持相同；切换距离衰减、左右到达时间和简化的远耳高频遮挡。该选项默认关闭。</p>',
    cases=cases, methods={'legacy':'原有声像','propagation':'几何直达声'}, extra=extra,
    footer='<p><a href="V014直达声传播.md">实现与验证范围</a> · <a href="V013试听.html">V0.13 驾驶对照</a> · <a href="V011试听.html">V0.11 音色对照</a></p><p class="quiet">本机工具：E:\\VehicleSoundLab\\Launch.cmd → Sound detail → Source distance / stereo depth。可随时切回原有声像。</p>')
(ROOT/'research/V014试听.html').write_text(page, encoding='utf-8')
print('Written six-case V014 optional direct-path review.')
