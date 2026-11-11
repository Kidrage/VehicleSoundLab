"""Simple focused startup review; no automatic playback."""
import json
from runtime_review import ROOT
from comparison_page import comparison_page
OUT=ROOT/'renders/v0.10.0'
report=json.loads((OUT/'verification.json').read_text())
labels={'start':'启动至怠速 · 完整混音','pure_start':'启动至怠速 · Pure OSC（没有启动机等辅助层）',
    'neutral':'启动后空挡补油','drive':'运动自动挡 · 30 秒驾驶','shifts':'手动换挡、收油与关闭点火'}
cases={}
for name,label in labels.items():
    takes=report['cases'][name]
    cases[name]=dict(label=label,takes={tag:'../renders/v0.10.0/'+takes[tag]['audition']['file'] for tag in ['v09','v010']},
        gain_note=f'本组新旧版共同固定增益 {takes["v010"]["audition"]["gain_db"]:+.2f} dB；固定种子 48271。没有单独归一化、压缩或降噪。驾驶输入相同；新版启动过程本身会改变后续振荡器相位。')
extra='''<p>先比较前 1 秒：启动机拖动之后，转速是否被逐渐带起，再落回怠速。新版不再在着车入口直接跳到高转速；启动时六层的音色增强也随带起／回落变化。主排气的稳态谱形没有重新拟合，不能把启动改善当作高转真实度验收。</p>
<details><summary>查看启动控制与参考证据</summary><img src="../renders/v0.10.0/lifecycle_comparison.png" alt="实际导出日志中的转速、排气和机械控制包络"><p class="quiet">旧日志较稀疏；新版记录启动期间每个渲染块。两者均为程序实际输出，不能直接对应参考车的转速。</p><img src="../references/analysis/lifecycle_v1/startup_observations.png" alt="批准参考启动段的原始立体声波形、频谱和频带能量"><img src="../references/analysis/lifecycle_v1/lifecycle_contact.jpg" alt="带原始 PTS 的启动过程视频帧"><p class="quiet">仪表布局变化与声音增强只能提供情境证据。独立音视频解码没有测得对齐偏差，360p 画面没有可靠转速遥测；0.28 秒拖动、0.20 秒带起、0.45 秒回落及 1150 RPM 均是工程设定。</p></details>
<details><summary>批准的实车参考</summary><p>A · Performante 33–40 s，车内启动情境。此录音位置与当前主目标的车外尾排不同，用于检查发声阶段；不用于直接拟合车外 EQ。</p><audio controls preload="metadata" data-reference src="../references/clean/A_start_context_v02.wav"></audio><p>A · 208–211 s，经过镜头核对的车外低转片段。后面的车内切镜部分已经排除；绝对 RPM 尚未确认。</p><audio controls preload="metadata" data-reference src="../references/clean/A_idle_context_v02.wav"></audio><p class="quiet">沿用固定 −6.0206 dB、28 Hz 高通、5 ms 端点淡化的已存试听副本；保留立体声，没有归一化或降噪。</p></details>'''
page=comparison_page(title='V0.10 · 连续启动',version='0.10.0',headline='从拖动、带起到回落，连续改变声音',
    intro='<p>启动过程拆成独立控制模块与参数配置。保持 DNA、轰鸣铺底、机械／气流及空间模块的分层，逐阶段驱动其响应。</p>',
    cases=cases,methods={'v09':'V0.9 · 原启动','v010':'V0.10 · 连续带起'},extra=extra,
    footer='<p><a href="V010连续启动.md">实现与验证</a> · <a href="V09试听.html">上一版压力音色对照</a></p><p class="quiet">实时界面：E:\\VehicleSoundLab\\Launch.cmd。启动参数仍是工程值，声线自然度与完整驾驶动力学目标继续推进。</p>')
(ROOT/'research/V010试听.html').write_text(page,encoding='utf-8')
print('Written V010 audition page.')
