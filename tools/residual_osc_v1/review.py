"""Create common-gain ablations, retaining the underlying DNA samples."""
import json
from pathlib import Path
from urllib.parse import quote
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from .spectrum import matrices


def write(workspace, fitted, output):
    report=json.loads((fitted/'report.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True,exist_ok=False)
    records,cards=[],[]
    for name,title in [('A_exterior','A · Performante 驻车车外'),('E_cabin','E · Performante 高转车内')]:
        root=fitted/name
        base,_=sf.read(root/'base_1.0.wav',always_2d=True)
        residual,_=sf.read(root/'residual_1.0.wav',always_2d=True)
        fixed,_=sf.read(root/'fixed_reference_float.wav',always_2d=True)
        variants=[('reference','固定音高的录音短参考',fixed),('base','只听 DNA',base),
                  ('half','DNA + 残差 50%',base+.5*residual),('full','DNA + 残差 100%',base+residual),
                  ('residual','只听新增残差',residual)]
        players=[]
        for key,label,audio in variants:
            audio=audio.copy()*.25
            fade=np.linspace(0,1,240)
            audio[:240]*=fade[:,None];audio[-240:]*=fade[::-1,None]
            assert np.isfinite(audio).all() and abs(audio).max()<.95
            target=output/f'{name}_{key}.wav';sf.write(target,audio,48000,subtype='PCM_24')
            records.append(dict(file=target.name,case=name,variant=key,frames=len(audio),sha256=sha(target),gain=.25,
                processing='Same total gain0.25;5ms end fades;PCM24. No EQ/limiter/per-variant gain matching.'))
            url=quote('../'+target.relative_to(workspace).as_posix(),safe='/.')
            players.append(f'<div><p>{label}</p><audio controls preload="metadata" src="{url}"></audio></div>')
        cards.append(f'<article><h2>{title}</h2>'+''.join(players)+'</article>')
    page=workspace/'research/谐波间残差OSC_V1.html';assert not page.exists()
    page.write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>谐波间残差 OSC V1</title><style>body{max-width:880px;margin:32px auto;padding:0 20px;background:#111820;color:#edf1f5;font:16px/1.6 system-ui}h1{font-size:27px}h2{font-size:21px}p{color:#c3ceda}article{background:#1c2733;border-radius:12px;padding:20px;margin:22px 0}audio{width:100%;max-width:100%}button{font:inherit;border:0;border-radius:7px;padding:8px 16px;cursor:pointer}</style>
<h1>谐波间细节 · OSC 残差 V1</h1>
<p>先比较“只听 DNA／残差50%／100%”，判断是否补回细节，或出现嘶声、砂感和金属感。两组分别取自车外与车内，参考录音已固定音高；它们不是相同录音位置。</p>
<p>统一输出增益0.25，没有逐条响度补偿。DNA样本保持相同，新增1.2–8kHz声层由独立OSC持续生成，没有录音循环；低频轰鸣不参与本次对照。</p>
<button id="stop">全部停止</button>
'''+''.join(cards)+'''<p>本轮只匹配固定片段的平均能量与左右关系，尚未拟合细节包络、完整驾驶工况或多声道声场，音色未通过听评。数值接近不等于自然度改善。</p>
<script>const players=[...document.querySelectorAll('audio')];players.forEach(a=>a.addEventListener('play',()=>players.forEach(b=>{if(b!==a)b.pause()})));document.getElementById('stop').onclick=()=>players.forEach(a=>a.pause());</script></html>''',encoding='utf-8')
    result=dict(page=str(page),page_sha256=sha(page),records=records,build_sha256=sha(fitted/'report.json'),human_accepted=False)
    (output/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
