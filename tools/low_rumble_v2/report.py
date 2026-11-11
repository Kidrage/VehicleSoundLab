"""Audition page and scientific plots from the retained LF evidence."""
import json
from urllib.parse import quote
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy import signal
from runtime_review import ROOT
from .analysis import OUT


def run():
    survey=json.loads((OUT/'survey.json').read_text(encoding='utf-8'))
    proof=json.loads((OUT/'verification.json').read_text(encoding='utf-8'));assert proof['result']=='pass'
    fig,axes=plt.subplots(4,1,figsize=(11,9),layout='constrained')
    for ax,(name,source) in zip(axes,survey['sources'].items()):
        windows=source['windows'];time=[v['seconds'][0] for v in windows]
        for band in ['20-40','40-80','80-150','150-250']:
            ax.plot(time,[v['bands_dbfs'][band] for v in windows],label=band+'Hz',linewidth=.8)
        ax.set(title=f'{name}: full decoded source ({source["duration_seconds"]:.2f}s)',ylabel='Band power / dBFS',ylim=(-80,0))
        ax.grid(alpha=.2);ax.legend(ncol=4,fontsize=8,loc='lower right')
    axes[-1].set_xlabel('Source time / s')
    fig.savefig(OUT/'all_sources_lf.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.8),layout='constrained')
    for name in ['A Exterior','B Cabin','D Dyno','E Cabin']:
        x,rate=sf.read(OUT/'renders'/f'{name}_low_raw.wav',always_2d=True)
        f,p=signal.welch(x[:,0],rate,nperseg=65536)
        ax.plot(f,10*np.log10(p+1e-30),label=name,linewidth=1)
    old,rate=sf.read(ROOT/'references/analysis/low_body_v1/renders/bass100_body_float.wav',always_2d=True)
    f,p=signal.welch(old[:,0]*2,rate,nperseg=65536)
    ax.plot(f,10*np.log10(p+1e-30),label='Previous three-tone LF (before0.5 monitor gain)',linewidth=.8,color='0.5')
    ax.set(xlim=(10,400),ylim=(-100,-20),xlabel='Frequency / Hz',ylabel='PSD / dBFS per Hz',title='Procedural LF source spectra (before common monitor gain0.5)')
    ax.legend(fontsize=8);ax.grid(alpha=.2);fig.savefig(OUT/'procedural_lf_spectra.png',dpi=160);plt.close(fig)
    names=['A Exterior','B Cabin','D Dyno','E Cabin']
    segment=['A_exterior_blips','B_cabin_pull','D_dyno_gears_context','E_sport_context']
    references={name:'../'+survey['segments'][seg]['lf_reference'] for name,seg in zip(names,segment)}
    titles={'A Exterior':'A · 车外尾排','B Cabin':'B · Tecnica 车内','D Dyno':'D · Performante 台架','E Cabin':'E · Performante 车内'}
    buttons=''.join(f'<button data-profile="{n}" aria-pressed="{str(i==0).lower()}">{titles[n]}</button>' for i,n in enumerate(names))
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>低频轰鸣 V2</title><style>
*{box-sizing:border-box}body{margin:0;background:#f6f5f1;color:#24282b;font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif}main{max-width:900px;margin:auto;padding:38px 24px}h1{font-size:30px;margin:0 0 12px}h2{font-size:21px;margin-top:32px}p{color:#545a5d}button{font:inherit;border:1px solid #c9cecb;border-radius:8px;padding:9px 14px;background:white;color:#263631;cursor:pointer}button[aria-pressed=true]{background:#234b40;border-color:#234b40;color:white}.row{display:flex;gap:9px;flex-wrap:wrap;margin:12px 0}.card{background:#fff;padding:22px;border:1px solid #e2e3dd;border-radius:13px}audio{display:block;width:100%;margin-top:18px}#now{font-weight:600}#error{color:#922}img{display:block;width:100%;height:auto;margin-top:16px}small{color:#656c68}summary{cursor:pointer}a{color:#28594a}
</style><main><h1>低频轰鸣 V2</h1><p>先暂停其他发声窗口。建议从 A 开始比较 40%／60%／80%，再单听低频；DNA 与输出增益始终相同。</p>
<div class="card"><div class="row">PROFILE_BUTTONS</div><div class="row">
<button data-method="dna" aria-pressed="false">只听 DNA</button><button data-method="040" aria-pressed="false">轰鸣 40%</button><button data-method="060" aria-pressed="true">轰鸣 60%</button><button data-method="080" aria-pressed="false">轰鸣 80%</button><button data-method="solo" aria-pressed="false">只听轰鸣</button></div>
<div id="now"></div><div id="host"></div><div class="row"><button id="transport">播放</button><label><input id="repeat" type="checkbox"> 循环试听</label></div><p id="error" role="alert"></p>
<small>合成持续声为新生成的 8 秒，循环开关只用于本页试听。低频单听沿用实际混音电平；各版本未单独补偿响度。</small></div>
<h2>回听来源</h2><p>A、B、D、E 分别保留各自的低频轮廓。录音参考是 25–280 Hz 滤出的混合声，保持录音电平与统一衰减，不能把它当作分离的纯发动机声。</p><div class="row"><button data-method="reference" aria-pressed="false">当前素材 · 录音低频参考</button><button data-method="old" aria-pressed="false">旧三低音 + 同一 DNA</button></div>
<details><summary>查看分析图与说明</summary><p>四份完整素材共约 23.5 分钟已做低频数值扫描。主听感是否更厚、更少嗡鸣，仍以试听为准。</p><img src="../references/analysis/low_rumble_v2/all_sources_lf.png" alt="四份全时长素材低频频段能量"><img src="../references/analysis/low_rumble_v2/procedural_lf_spectra.png" alt="四种新低频轮廓和旧三低音的频谱"><p><a href="低频轰鸣V2.md">方法与验证记录</a></p></details>
<script src="../tools/seekable_review_player_v1.js"></script><script>
const references=REFERENCE_DATA,titles=TITLE_DATA;
let profile='A Exterior',method='060';
function selectedSource(){const base='../references/analysis/low_rumble_v2/renders/';if(method==='reference')return references[profile];if(method==='old')return base+'old_three_tone_same_DNA.wav';if(method==='solo')return base+profile+'_solo_audition.wav';return base+profile+'_mix'+(method==='dna'?'000':method)+'_audition.wav';}
const player=new SeekableReviewPlayer(document.getElementById('host'),document.getElementById('transport'),text=>document.getElementById('error').textContent=text);
function select(preserve=true){document.getElementById('error').textContent='';player.select(selectedSource(),preserve);player.current.audio.loop=document.getElementById('repeat').checked;document.getElementById('now').textContent=titles[profile]+' · '+document.querySelector('[data-method="'+method+'"]').textContent;document.querySelectorAll('[data-profile]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.profile===profile)));document.querySelectorAll('[data-method]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.method===method)));}
document.querySelectorAll('[data-profile]').forEach(b=>b.onclick=()=>{profile=b.dataset.profile;select();});document.querySelectorAll('[data-method]').forEach(b=>b.onclick=()=>{method=b.dataset.method;select();});document.getElementById('repeat').onchange=e=>player.current.audio.loop=e.target.checked;select(false);
</script></main></html>'''
    html=html.replace('PROFILE_BUTTONS',buttons).replace('REFERENCE_DATA',json.dumps(references,ensure_ascii=False)).replace('TITLE_DATA',json.dumps(titles,ensure_ascii=False))
    (ROOT/'research/低频轰鸣V2.html').write_text(html,encoding='utf-8')
    print('Created low-rumble review page and two evidence plots.')
