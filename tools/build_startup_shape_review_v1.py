"""One-player, same-gain comparison of fixed reference and actual C candidates."""
import argparse
import html
import json
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from event_designer.package import write_json
from event_authoring.audio import read,sha
from inspect_startup_shape_v1 import curves


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    root=Path('E:/VehicleSoundLab/references/analysis/startup_shape_v1');rows=[]
    def track(label,path,name,description):
        x,sr=sf.read(path,always_2d=True);sf.write(out/name,x*.25,sr,subtype='FLOAT')
        rows.append(dict(label=label,file=name,description=description,frames=len(x),channels=x.shape[1],sha256=sha(out/name),gain=.25))
    context,rate,_=read(Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav'),35.,40.5)
    sf.write(out/'raw-context.wav',context,rate,subtype='FLOAT')
    track('原素材 · 启动上下文',out/'raw-context.wav','reference-context.wav','A录音35–40.5秒，车内混合观察；用于核对动作。')
    track('原素材 · 接火选区',root/'candidate2/analysis/reference.wav','reference-event.wav','固定37.22–38.02秒；未做背景波形分离。')
    track('C接火 · 原包络',root/'diagnosis2/original-C.wav','original-event.wav','所有正弦模态共用起音。')
    track('C接火 · 分频起音候选',root/'candidate2/27431/synthesis.wav','candidate-event.wav','300–1200Hz约0.343秒起音；同段素材重新校准成分电平。')
    track('C完整启动 · 原包络',root/'verification2/V11-original/mix.wav','original-startup.wav','8秒工程流程；启动→接火→怠速。')
    track('C完整启动 · 分频起音候选',root/'verification2/V11-candidate/mix.wav','candidate-startup.wav','仅接火事件参数不同；连续DNA、低频与怠速声源相同。')
    # Keep explicit recipes and deterministic takes with the review.
    for prefix,variant in [('original','V11-original'),('candidate','V11-candidate')]:
        for file,label in [('startup.recipe.json','preset.json'),('lifecycle.vsltake.json','take.json')]:
            shutil.copy2(root/'verification2'/variant/file,out/f'{prefix}.{label}')
    raw,_=sf.read(root/'candidate2/analysis/reference.wav',always_2d=True)
    master,_,_=read(Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav'),35.,36.2)
    t,reference=curves(raw);_,bg=curves(master);reference=np.maximum(reference-bg.mean(axis=1)[:,None],0)
    old,_=sf.read(root/'diagnosis2/original-C.wav');_,old=curves(old[:len(raw)])
    new,_=sf.read(root/'candidate2/27431/synthesis.wav');_,new=curves(new[:len(raw)])
    fig,axes=plt.subplots(2,2,figsize=(10,6),constrained_layout=True)
    for k,ax in enumerate(axes.flat,start=1):
        ax.plot(t,reference[k],label='Recorded acoustic excess');ax.plot(t,old[k],label='Original C');ax.plot(t,new[k],label='Candidate C')
        ax.set(title=['60–300 Hz','300–1200 Hz','1200–4500 Hz','4500–14000 Hz'][k-1],xlabel='Seconds from fixed crop',ylabel='FS²');ax.legend(fontsize=7);ax.grid(alpha=.2)
    fig.savefig(out/'envelopes.png',dpi=140);plt.close(fig)
    buttons=''.join(f'<button data-track="{i}">{html.escape(r["label"])}</button>' for i,r in enumerate(rows))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>启动分频起音 · C对照</title>
<style>body{max-width:980px;margin:32px auto;padding:0 20px;background:#111815;color:#e3ebe2;font:16px/1.65 system-ui}h1{font-size:25px}button,a{color:inherit}button{background:#26342b;border:1px solid #718469;padding:12px;margin:5px;cursor:pointer}button[aria-pressed=true]{background:#425e36}audio{width:100%}img{width:100%}small{color:#b8c4b5}a{color:#bddea6}.tracks{display:flex;flex-wrap:wrap}#status{min-height:54px}</style>
<h1>启动分频起音 · 实际C对照</h1><p>先听接火的原包络／新候选，再听完整启动。只有一个播放器，均额外衰减12 dB，无逐条归一化、房间处理或限幅。</p>
<p>这次改善的是能量建立顺序：保留快速高频起音，让中低频逐渐建立。原录音的多次高频起伏仍未还原；新候选尚未获得听感认可。</p>
<div class="tracks">BUTTONS</div><p id="status">选择声音后播放</p><audio id="player" controls preload="none"></audio><p><a id="download" download>下载当前试听</a></p>
<p><small>完整C示范由A车外持续DNA、F2怠速、A车内启动事件组成，控制器启动信号在0.35秒；拖转时长0.58秒是工程设定，不是实测物理RPM／时长，也不是同一视角的录音重建。</small></p>
<p><a href="candidate.preset.json" download>候选控制台配方（V11）</a> · <a href="candidate.take.json" download>候选确定性行程（V11）</a> · <a href="original.preset.json" download>原包络配方（V11）</a></p>
<img src="envelopes.png" alt="原录音统计增量、原C和候选C分频能量建立对照"><script>
const tracks=ROWS,player=document.querySelector('#player');let currentURL=null,request=0;
document.querySelectorAll('[data-track]').forEach(b=>b.onclick=async()=>{const ticket=++request,row=tracks[Number(b.dataset.track)],running=!player.paused,time=player.currentTime;player.pause();document.querySelector('#status').textContent='载入中…';try{const response=await fetch(row.file);if(!response.ok)throw Error(response.status);const blob=await response.blob();if(ticket!==request)return;const url=URL.createObjectURL(blob);if(currentURL)URL.revokeObjectURL(currentURL);currentURL=url;player.src=url;player.onloadedmetadata=()=>{if(ticket!==request)return;player.currentTime=Math.min(time,Math.max(0,player.duration-.02));if(running)player.play();};document.querySelector('#status').textContent=row.label+' · '+row.description;const a=document.querySelector('#download');a.href=row.file;a.download=row.file;document.querySelectorAll('[data-track]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));}catch(e){document.querySelector('#status').textContent=String(e);}});
window.addEventListener('pagehide',()=>{if(currentURL)URL.revokeObjectURL(currentURL);});
</script></html>'''
    page=page.replace('BUTTONS',buttons).replace('ROWS',json.dumps(rows,ensure_ascii=False))
    (out/'index.html').write_text(page,encoding='utf-8');write_json(out/'tracks.json',rows)
    print(str(out/'index.html'),flush=True)


if __name__=='__main__':main()
