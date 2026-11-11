"""Shared-gain listening references for the state-colour diagnostic."""
import html
from pathlib import Path
from urllib.parse import quote
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha


def write(workspace, observed, report, output):
    output.mkdir(parents=True, exist_ok=False)
    records, cards = [], []
    labels = {'fall1':'第一次声线下落', 'rise2':'第二次声线上升', 'fall2':'第二次声线下落'}
    for name, evidence in report['cases'].items():
        players = []
        for filename, label in [('normalized_float.wav','固定声学音高的录音短参考'),
                                ('c_sustained_float.wav','同一 C 核心持续生成 · 8 秒')]:
            source = observed/name/filename
            audio, rate = sf.read(source, always_2d=True)
            assert rate == 48000 and audio.shape[1] == 2 and np.isfinite(audio).all()
            audio = audio.copy()*.25
            fade = np.linspace(0, 1, min(240, len(audio)//2))
            audio[:len(fade)] *= fade[:, None]
            audio[-len(fade):] *= fade[::-1, None]
            assert abs(audio).max() < .95
            target = output/(name+'_'+filename.replace('_float',''))
            sf.write(target, audio, rate, subtype='PCM_24')
            records.append(dict(file=str(target.relative_to(workspace)).replace('\\','/'),
                source=str(source.relative_to(workspace)).replace('\\','/'), source_sha256=sha(source),
                sha256=sha(target), frames=len(audio), gain=.25,
                processing='Shared gain0.25;5ms endpoint fades;PCM24; no per-variant matching/EQ/loop'))
            url = quote('../'+target.relative_to(workspace).as_posix(), safe='/.')
            players.append(f'<p>{label}</p><audio controls preload="metadata" src="{url}"></audio>')
        start, stop = evidence['correction']['source_seconds']
        cards.append(f'<article><h2>{labels[name]}</h2><p>源时间 {start:.3f}–{stop:.3f} 秒；'
            f'{evidence["normalized_cycles"]:.1f} 个周期。连续生成器使用相同协议和二进制。</p>{"".join(players)}</article>')
    page = workspace/'research/工况声纹分离V1.html'
    assert not page.exists()
    picture = quote('../'+(observed/'spectra.png').relative_to(workspace).as_posix(), safe='/.')
    page.write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>工况声纹分离 V1</title><style>body{max-width:900px;margin:32px auto;padding:0 20px;background:#111820;color:#e9edf2;font:16px/1.65 system-ui}h1{font-size:27px}h2{font-size:20px}article,details{padding:18px;background:#1b2632;border-radius:10px;margin:18px 0}audio,img{width:100%;max-width:100%}p{color:#c2ccd8}summary{cursor:pointer}</style>
<h1>同一音高下，驻车起落声纹有什么不同</h1>
<p>A 已批准素材，同一驻车后侧视角。所有声音统一到声学根频率 46.875 Hz，固定总增益 0.25，没有逐条响度补偿；无自动播放。</p>
<p>这是分析复核页。上升段只有约 7 个周期，统计独立性不足，尚未接入驾驶。声线上升／下落不等于已测负载、松油或断油。</p>
'''+''.join(cards)+f'<details><summary>查看谱形诊断</summary><img src="{picture}" alt="相同声学音高的谐波谱形比较"></details>'+
'''<p>主要观察为相近根频率区间的 400–1200 Hz 差异。高频在两次下落中也变化，8–14kHz 另受分析带宽限制，不能用这组数据宣称已完成工况标定。C 音频未使用短参考循环，短参考只播放一次。</p>
<script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(b!==a)b.pause()})))</script></html>''',encoding='utf-8')
    return dict(page=str(page), records=records, page_sha256=sha(page), human_accepted=False)
