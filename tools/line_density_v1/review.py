"""Shared-gain listening artifacts; no question or acceptance is generated."""
import html
import numpy as np
import soundfile as sf


def save_review(out,recordings,plan):
    start=round(plan['review_start_seconds']*48000);count=round(plan['review_seconds']*48000)
    folder=out/'audition';folder.mkdir()
    files={}
    for name,audio in recordings.items():
        clip=audio[start:start+count].copy()
        fade=np.ones(len(clip));fade[:240]=np.linspace(0,1,240);fade[-240:]=np.linspace(1,0,240)
        clip*=plan['output_gain']*fade[:,None]
        peak=float(abs(clip).max());assert peak<plan['tolerances']['review_peak_maximum']
        sf.write(folder/(name+'.wav'),clip,48000,subtype='PCM_24')
        files[name]=dict(frames=len(clip),peak=peak,rms=float(np.sqrt(np.mean(clip**2))))
    return files


def page(workspace,out,plan):
    prefix='../references/analysis/line_density_v1/'+out.name+'/audition/'
    groups=[('完整声音',[('accepted','认可基准'),('density_0','仅补原有频带差额'),
        ('density_25','高频密度候选 A'),('density_50','高频密度候选 B')]),
        ('单听细节层',[('cloud_0','原差额细节'),('cloud_25','候选 A 细节'),('cloud_50','候选 B 细节')])]
    sections=[]
    for title,variants in groups:
        cards=''.join('<div class="card"><label>'+html.escape(label)+'</label><audio controls preload="metadata" src="'+
            prefix+key+'.wav"></audio></div>' for key,label in variants)
        sections.append('<section><h2>'+title+'</h2>'+cards+'</section>')
    body='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    body+='<title>高频密度对照 V1</title><style>body{font:16px/1.6 system-ui;max-width:840px;margin:32px auto;padding:0 20px;background:#f4f5f5;color:#20272b}h1{font-size:25px}h2{font-size:19px}.card{background:white;border:1px solid #dce1e3;border-radius:8px;padding:12px 16px;margin:10px 0}label{display:block;margin-bottom:8px}audio{width:100%;height:42px}details{margin-top:28px;font-size:14px}</style>'
    body+='<h1>高频密度对照 V1</h1><p>比较电子感、沙感和连续排气质感。请先暂停其他发声窗口，再逐条播放。</p><p>各版本使用相同输出增益和同一低频。这里是固定音高的持续生成，没有原录音循环。</p>'+''.join(sections)
    body+='<details><summary>实验范围</summary><p>仅来自 A 移动尾排固定情境；候选 A／B 是有界的高频谐波功率重分配（25%／50%，1.2–1.9kHz过渡），再由现有 C OSC 云拟合八带非负功率差额。比例是工程试验量，不是测得的噪声占比。没有逐版本响度归一化。</p><p>DNA和细节均由现有C声源生成，离线汇总。平均相位、低谐波与认可相干低频保留；未接入驾驶默认。此录音近双mono，不用于证明声场宽度。细节层仍有固定载波拍频，尚未新拟合时间包络。没有新的听评认可。</p></details>'
    body+='<script>document.querySelectorAll("audio").forEach(a=>a.addEventListener("play",()=>document.querySelectorAll("audio").forEach(b=>{if(a!==b)b.pause()})))</script></html>'
    target=workspace/'research/高频密度对照V1.html';target.write_text(body,encoding='utf-8',newline='\n')
    return target
