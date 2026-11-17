"""Same-gain A/B event comparisons and an actual complete V12 startup pair."""
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
from event_authoring.audio import read
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    root=Path('E:/VehicleSoundLab/references/analysis/event_joint_v1');rows=[]
    def add(label,x,name,description):
        if isinstance(x,Path):x,rate=sf.read(x,always_2d=True)
        else:rate=48000
        sf.write(out/name,x*.25,rate,subtype='FLOAT')
        rows.append(dict(label=label,file=name,description=description,frames=len(x),channels=x.shape[1] if x.ndim>1 else 1,sha256=sha(out/name),gain=.25))
    for key,context in [('A',(35.,40.5)),('B',(12.,20.))]:
        master=Path(f'E:/VehicleSoundLab/references/clean/{key}_decoded_float.wav')
        audio,_,_=read(master,*context);sf.write(out/f'{key}-raw-context.wav',audio,48000,subtype='FLOAT')
        add(f'{key} 原录音 · 动作上下文',audio,f'{key}-context.wav',f'原始录音{context[0]}–{context[1]}秒；用于核对动作与录音环境。')
        add(f'{key} 原录音 · 固定选区',root/f'verification2/{key}/analysis/reference.wav',f'{key}-reference.wav','未经波形去背景或物理声源分离。')
        add(f'{key} C · 上轮候选',root/f'audit2/{key}/original-27431.wav',f'{key}-original.wav','A为上轮多段包络；B为原持续门控候选。随机种子27431。')
        add(f'{key} C · 可靠频段联合拟合',root/f'verification2/{key}/C-27431.wav',f'{key}-candidate.wav','仅证据较强的高频段提取多段幅度包络；弱频段保留局部包络，所有已有成分重新校准幅度。')
        shutil.copy2(root/f'verification2/{key}/analysis/profile.json',out/f'{key}-candidate.parameters.json')
    for variant,label in [('original','上轮候选'),('candidate','联合拟合候选')]:
        add('完整启动 · '+label,root/f'startup1/{variant}/mix.wav',f'{variant}-startup.wav','8秒工程流程；只有接火事件参数不同，19个连续声源通道逐样本相同。')
        for filename,suffix in [('startup.recipe.json','preset.json'),('lifecycle.vsltake.json','take.json')]:
            shutil.copy2(root/f'startup1/{variant}/{filename}',out/f'{variant}.{suffix}')
    fig,axes=plt.subplots(2,2,figsize=(10,6),constrained_layout=True)
    for row,key in enumerate(('A','B')):
        data=np.load(root/f'audit2/{key}/curves.npz')
        for col,k in enumerate((3,4)):
            ax=axes[row,col]
            for field,label in [('target','Recorded acoustic excess'),('original','Previous C'),('candidate','Joint-fit C')]:
                power=data[field][k];ax.plot(data['time'],power/max(power.mean(),1e-30),label=label)
            contrast=data['contrast_db'][k]
            ax.set(title=f'{key}: {[(1200,4500),(4500,14000)][col]} Hz; contrast {contrast:.2f} dB',xlabel='Seconds from fixed crop',ylabel='Power / own mean')
            ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.savefig(out/'curves.png',dpi=140);plt.close(fig)
    buttons=''.join(f'<button data-track="{i}">{html.escape(r["label"])}</button>' for i,r in enumerate(rows))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>启动事件 · 可靠频段联合拟合</title>
<style>body{max-width:980px;margin:32px auto;padding:0 20px;background:#111815;color:#e3ebe2;font:16px/1.65 system-ui}h1{font-size:25px}button{color:inherit;background:#26342b;border:1px solid #718469;padding:12px;margin:5px;cursor:pointer}button[aria-pressed=true]{background:#425e36}audio,img{width:100%}small{color:#b8c4b5}a{color:#bddea6}.tracks{display:flex;flex-wrap:wrap}#status{min-height:54px}</style>
<h1>启动事件 · 可靠频段联合拟合</h1><p>先比较B的上轮／联合拟合，再听A和完整启动。所有试听固定乘0.25，无逐条归一化、房间处理或限幅，只有一个播放器。</p>
<p>这一轮修复提参：极小的旧幅度不再锁死后续校准；只在事件相对背景足够清楚的高频段提取时间起伏。运行时仍由正弦模态、程序纹理与包络合成，不回放录音。</p>
<div class="tracks">BUTTONS</div><p id="status">选择声音后播放</p><audio id="player" controls preload="none"></audio><p><a id="download" download>下载当前试听</a></p>
<p><small>B的1.2–4.5kHz平均能量低于背景约2.15dB，所以保留原有局部包络，并不判定该频段没有发动机声。B的4.5–14kHz时间细节仍有明显差距。A相对上轮最高频起伏误差略增，不是全面升级；新候选均尚未获得听感认可。</small></p>
<p><small>完整启动仍为A车外持续DNA＋F2怠速＋A混合录音启动事件的工程示范，0.58秒拖转和RPM为工程设定。B车内事件独立比较，没有混入这组完整启动。</small></p>
<p><a href="A-candidate.parameters.json" download>A事件参数</a> · <a href="B-candidate.parameters.json" download>B事件参数</a> · <a href="candidate.preset.json" download>完整候选V12配方</a> · <a href="candidate.take.json" download>确定性行程</a> · <a href="original.preset.json" download>上轮配方</a></p>
<p>下图比较各频段除以自身均值后的时间形状；频谱总能量另行校验，二者没有混作同一绝对目标。</p><img src="curves.png" alt="两份素材的高频起伏与实际C对照"><script>
const tracks=ROWS,player=document.querySelector('#player');let currentURL=null,request=0;
document.querySelectorAll('[data-track]').forEach(b=>b.onclick=async()=>{const ticket=++request,row=tracks[Number(b.dataset.track)],running=!player.paused,time=player.currentTime;player.pause();document.querySelector('#status').textContent='载入中…';try{const response=await fetch(row.file);if(!response.ok)throw Error(response.status);const blob=await response.blob();if(ticket!==request)return;const url=URL.createObjectURL(blob);if(currentURL)URL.revokeObjectURL(currentURL);currentURL=url;player.src=url;player.onloadedmetadata=()=>{if(ticket!==request)return;player.currentTime=Math.min(time,Math.max(0,player.duration-.02));if(running)player.play();};document.querySelector('#status').textContent=row.label+' · '+row.description;const a=document.querySelector('#download');a.href=row.file;a.download=row.file;document.querySelectorAll('[data-track]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));}catch(e){document.querySelector('#status').textContent=String(e);}});
window.addEventListener('pagehide',()=>{if(currentURL)URL.revokeObjectURL(currentURL);});
</script></html>'''
    (out/'index.html').write_text(page.replace('BUTTONS',buttons).replace('ROWS',json.dumps(rows,ensure_ascii=False)),encoding='utf-8')
    save(out/'tracks.json',rows);print(str(out/'index.html'),flush=True)


if __name__=='__main__':main()
