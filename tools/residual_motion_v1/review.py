"""Shared-gain ablations for the accepted exterior pair and optional residual."""
import json
from urllib.parse import quote
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha


def write(workspace, fitted, verified, out):
    report = json.loads((verified/'verification.json').read_text(encoding='utf-8'))
    assert report['result'] == 'pass' and report['fit_sha256'] == sha(fitted/'report.json')
    out.mkdir(parents=True, exist_ok=False)

    def read(path):
        x, rate = sf.read(path, always_2d=True)
        assert rate == 48000 and x.shape[1] == 2 and np.isfinite(x).all()
        return x

    base = read(fitted/'accepted_pair.wav')
    fixed = read(fitted/'reference.wav')
    static = read(verified/'A_pitch1.0_amount0.wav')
    half = read(verified/'A_amount_half.wav')
    full = read(verified/'A_pitch1.0_amount1.wav')
    assert base.shape == static.shape == half.shape == full.shape
    variants = [('reference', '固定音高录音 · 短参考', fixed),
                ('accepted', '已认可 DNA + 相干低频', base),
                ('static', '加入静态细节 OSC', base+static),
                ('half', '加入细节 OSC · 幅度变化 50%', base+half),
                ('full', '加入细节 OSC · 幅度变化 100%', base+full),
                ('solo_static', '静态细节 OSC · 独奏', static),
                ('solo_full', '幅度变化 100% · 细节独奏', full)]
    records, cards = [], []
    for key, label, audio in variants:
        audio = audio.copy()*.5
        fade = np.linspace(0, 1, 240)
        audio[:240] *= fade[:, None]
        audio[-240:] *= fade[::-1, None]
        assert abs(audio).max() < .95
        path = out/(key+'.wav')
        sf.write(path, audio, 48000, subtype='PCM_24')
        records.append(dict(file=path.name, variant=key, frames=len(audio), sha256=sha(path),
                            gain=.5, peak=float(abs(audio).max()),
                            processing='Common gain0.5;5ms fades;PCM24; no per-item matching/EQ/limiter'))
        url = quote('../'+path.relative_to(workspace).as_posix(), safe='/.')
        cards.append(f'<article><h2>{label}</h2><audio controls preload="metadata" src="{url}"></audio></article>')
    page = workspace/'research/残差幅度细节V1.html'
    assert not page.exists()
    page.write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>细节幅度变化 V1</title>
<style>body{max-width:800px;margin:32px auto;padding:0 20px;background:#111820;color:#edf1f5;font:16px/1.6 system-ui}h1{font-size:27px}h2{font-size:19px}p{color:#c3ceda}article{background:#1c2733;border-radius:12px;padding:18px;margin:18px 0}audio{width:100%}button{font:inherit;border:0;border-radius:7px;padding:9px 16px;cursor:pointer}</style>
<h1>细节幅度变化 · V1</h1>
<p>先比较静态细节与幅度变化50%／100%，再听两条独奏。关注是否更自然，或增加了呼吸、颤动与砂感；也可能基本听不出差别。</p>
<p>这次保留已认可的DNA与相干低频，只改变新增细节的幅度。全部使用同一增益，没有逐条响度补偿。录音短参考与其余8秒持续生成声的长度不同。</p>
<button id="stop">全部停止</button>
'''+''.join(cards)+'''
<p>本轮是幅度变化诊断，数值尚未显示明确改善，音色待听评。加入细节会增加能量；与干声的差别不能单独证明自然度提高。</p>
<script>const players=[...document.querySelectorAll('audio')];players.forEach(a=>a.addEventListener('play',()=>players.forEach(b=>{if(b!==a)b.pause()})));document.getElementById('stop').onclick=()=>players.forEach(a=>a.pause());</script></html>''', encoding='utf-8')
    result = dict(page=str(page), page_sha256=sha(page), records=records,
                  fit_sha256=sha(fitted/'report.json'), verification_sha256=sha(verified/'verification.json'),
                  human_accepted=False, timbre_improvement='not_established')
    (out/'review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return result
