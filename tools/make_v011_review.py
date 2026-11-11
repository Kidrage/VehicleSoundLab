"""Focused spectrum-continuity listening page and explicit source solo gains."""
import json
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf
from review_pairs import common_pair
from comparison_page import comparison_page
OUT=ROOT/'renders/v0.11.0'
r=json.loads((OUT/'verification.json').read_text())
labels={'low':'完整混音 · 1200 RPM 低转','mid':'完整混音 · 4000 RPM 带载','high':'完整混音 · 8000 RPM 带载',
    'idle':'完整混音 · 850 RPM 工程怠速','pure_low':'Pure OSC · 1200 RPM／零循环变化',
    'lift':'固定 5000 RPM · 收油／恢复','neutral':'空挡补油','downshift':'制动降挡补油','drive':'运动自动挡 · 30 秒驾驶'}
cases={}
for name,label in labels.items():
    takes=r['cases'][name]
    cases[name]=dict(label=label,takes={tag:'../renders/v0.11.0/'+takes[tag]['audition']['file'] for tag in ['v010','v011']},
        gain_note=f'本组共同固定增益 {takes["v011"]["audition"]["gain_db"]:+.2f} dB；新旧驾驶轨迹、空间设置相同。没有分别归一化、压缩或降噪。')
r['isolated']={}
for name in ['low','mid','high']:
    arrays=[np.column_stack([sf.read(OUT/f'stems/{name}_{tag}_exhaust_{side}.wav')[0] for side in ['left','right']]) for tag in ['v010','v011']]
    pair=common_pair(OUT,arrays,['v010','v011'],'banks_'+name);r['isolated'][name]=pair
    for item in pair.values():r['files'][item['file']]=item['sha256']
    cases['banks_'+name]=dict(label='两排气源独奏 · '+labels[name].split(' · ')[1],
        takes={tag:'../renders/v0.11.0/'+pair[tag]['file'] for tag in ['v010','v011']},
        gain_note=f'本组共同固定增益 {pair["v011"]["gain_db"]:+.2f} dB。两个排气声源分别放在 L／R；没有监听位置的空间处理，不是双耳录音。')
(OUT/'verification.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
extra='''<p>先听 1200／4000 RPM，再听 8000 RPM 与收油过渡。新版从低阶 DNA 延续主谐波的强弱，再逐渐转到高频细节。高转部分的变化也可能让你觉得更柔或更薄；请以听感判断是否值得保留。</p>
<p class="quiet">当前修正的是程序两条合成路径之间的谱形断口，尚未完成实车谱形标定。参考中的主谱线不能直接当作发动机转速；默认怠速没有依据这次估计改动。</p>
<details><summary>查看实际导出的频谱与参考观测</summary><img src="../renders/v0.11.0/spectral_handoff.png" alt="旧版与新版在五种转速、两种负载下的实际主缸列谐波幅度"><p class="quiet">虚线 V0.10，实线 V0.11；测量主缸列谐波，不是完整的实车谐波谱。数字连续性不代表自然度。</p><img src="../references/analysis/order_families_v1/spectral_families.png" alt="三段已核对车外参考的原始频谱与自动间距候选"><p class="quiet">青线为自动频率间距候选及其倍频，会出现倍频／分频误判，尤其是快速补油段。没有据此给实车赋予 RPM 或踏板标签；原始声道保持独立。</p></details>
<details><summary>批准的车外参考</summary><p>A · Performante 208–211 s，车外低转；已排除后面的车内切镜。</p><audio controls preload="metadata" data-reference src="../references/clean/A_idle_context_v02.wav"></audio><p>A · 238–248 s，驻车尾部补油情境，驾驶门打开；实际挡位、转速和负载未确认。</p><audio controls preload="metadata" data-reference src="../references/clean/A_corsa_tailpipe_blips.wav"></audio><p class="quiet">沿用固定 −6.0206 dB、28 Hz 高通、5 ms 端点淡化，未归一化或降噪。与合成版本没有做响度匹配。</p></details>'''
page=comparison_page(title='V0.11 · 排气谱形衔接',version='0.11.0',headline='让低阶与高阶之间的声线连起来',
    intro='<p>优先比较低转／中转的完整混音，再切换高转和收油。每组新旧版使用共同增益，保留电平与动态差异。</p>',
    cases=cases,methods={'v010':'V0.10 · 原高阶入口','v011':'V0.11 · 延续主谐波'},extra=extra,
    footer='<p><a href="V011排气谱形衔接.md">实现与验证</a> · <a href="V010试听.html">上一版启动对照</a></p><p class="quiet">实时界面：E:\\VehicleSoundLab\\Launch.cmd。High firing orders 控制高阶延伸；0.55 为本次默认比较位置。旧版程序与音频继续保留。</p>')
(ROOT/'research/V011试听.html').write_text(page,encoding='utf-8')
print('Written V011 review with nine mixes and three source pairs.')
