"""Write review-only endpoint fades; no per-variant level matching or widening."""
import html
import numpy as np
import soundfile as sf
from .validate import read


def make(workspace, output):
    directory = output / 'audition'
    directory.mkdir()
    cases = [
        ('reference', 'pair_dry_dry', '认可组合 · 直送监听'),
        ('pair', 'pair_dry_render', '双出口投影 · 无房间'),
        ('room', 'pair_room_render', '双出口投影 · 加房间'),
        ('geometry', 'pair_geometry_render', '双出口投影 · 几何传播'),
        ('left', 'left_geometry_render', '诊断：仅左出口 · 几何传播'),
        ('right', 'right_geometry_render', '诊断：仅右出口 · 几何传播'),
        ('warm', 'warm_render', '通用性检查：Warm 合成测试音'),
        ('hollow', 'hollow_render', '通用性检查：Hollow 合成测试音')
    ]
    cards = []
    for key, source, label in cases:
        audio = read(output / 'raw' / (source + '.wav')).astype('float64')
        fade = np.ones(len(audio))
        fade[:240] = np.linspace(0, 1, 240)
        fade[-240:] = np.linspace(1, 0, 240)
        sf.write(directory / (key + '.wav'), audio * fade[:, None], 48000, subtype='PCM_24')
        url = '../references/analysis/' + output.name + '/audition/' + key + '.wav'
        cards.append(f'<div class="card"><label for="{key}">{html.escape(label)}</label><audio id="{key}" controls preload="metadata" src="{url}"></audio></div>')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DNA 与低频 · 空间接入 V1</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:800px;margin:30px auto;padding:0 20px;background:#f4f5f5;color:#20272b}h1{font-size:25px}h2{font-size:19px}.card{padding:12px 16px;margin:12px 0;background:white;border:1px solid #dce1e3;border-radius:8px}label{display:block;margin-bottom:8px}audio{width:100%;height:42px}details{font-size:14px;margin:24px 0}</style>
<h1>DNA 与低频 · 空间接入 V1</h1><p>先听“认可组合 · 直送监听”，再比较无房间与加房间的双出口投影。关注空间处理是否带来空洞、梳状感或音色退化。</p>
<p>全部沿用相同 DNA 与实测相位低频；未额外增亮、失谐或逐版匹配响度。投影和距离会改变音量，请同时留意这一点。</p><h2>组合与空间</h2>'''
    page += ''.join(cards[:4]) + '<h2>出口定位诊断</h2><p>仅左／仅右用于核对位置，不代表已分离录音中的左右缸组。</p>' + ''.join(cards[4:6])
    page += '<details><summary>同一系统的其他谱形与技术范围</summary><p>下列两条是工程合成测试音，使用同一生成器与空间适配器，没有新增实车还原结论。</p>' + ''.join(cards[6:])
    page += '<p>本轮仍为固定声学情境，未映射完整 RPM／负载。录音观察近乎双单声道；双出口是明确设计投影，每个出口分配一半幅度，不是声源分离。空间层使用现有工程模型，含28Hz高通和120Hz分频；房间与几何传播均未实测标定。12通道文件另存，浏览器只提供立体声试听。高度通道仅包含房间反射。</p></details>'
    page += '<script>document.querySelectorAll("audio").forEach(a=>a.addEventListener("play",()=>document.querySelectorAll("audio").forEach(b=>{if(b!==a)b.pause()})))</script></html>'
    path = workspace / 'research/DNA空间接入V1.html'
    if path.exists():
        raise FileExistsError(path)
    path.write_text(page, encoding='utf-8')
    return path
