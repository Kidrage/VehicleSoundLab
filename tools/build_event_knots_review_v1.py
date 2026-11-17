"""Ten same-gain tracks: approved reference crops, actual events and full startup."""
import argparse
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from event_authoring.audio import read
from event_review import page
from research_archive_v1 import save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    root=Path('E:/VehicleSoundLab/references/analysis');study=root/'event_knots_v1';tracks=[]
    def add(label,path,name,description):
        x,rate=sf.read(path,always_2d=True);sf.write(out/name,x*.25,rate,subtype='FLOAT')
        tracks.append(dict(label=label,file=name,description=description,gain=.25,frames=len(x),channels=x.shape[1],sha256=sha(out/name)))
    for key,context in [('A',(35.,40.5)),('B',(12.,20.))]:
        raw,rate,_=read(Path(f'E:/VehicleSoundLab/references/clean/{key}_decoded_float.wav'),*context)
        sf.write(out/f'{key}-raw-context.wav',raw,rate,subtype='FLOAT')
        add(key+' 原录音 · 动作上下文',out/f'{key}-raw-context.wav',f'{key}-context.wav','用于核对原始动作与录音环境；没有做波形去背景。')
        add(key+' 原录音 · 固定选区',study/f'verification1/{key}/analysis/reference.wav',f'{key}-reference.wav','与上轮使用相同选区。')
        add(key+' C · 上轮固定控制点',root/f'event_joint_v1/verification2/{key}/C-27431.wav',f'{key}-original.wav','可靠频带联合拟合；随机种子27431。')
        add(key+' C · 自适应控制点',study/f'verification1/{key}/C-27431.wav',f'{key}-candidate.wav','控制点数量不变，按声纹起伏选择时间位置；运行时仍为同一C合成器。')
        shutil.copy2(study/f'verification1/{key}/analysis/profile.json',out/f'{key}-candidate.parameters.json')
    for variant,label in [('original','上轮固定控制点'),('candidate','自适应控制点')]:
        add('完整启动 · '+label,study/f'startup1/{variant}/mix.wav',f'{variant}-startup.wav','8秒工程流程；只替换A接火事件参数，19个连续通道逐样本保持。')
        for file,suffix in [('startup.recipe.json','preset.json'),('lifecycle.vsltake.json','take.json')]:
            shutil.copy2(study/f'startup1/{variant}/{file}',out/f'{variant}.{suffix}')
    fig,axes=plt.subplots(2,2,figsize=(10,6),constrained_layout=True)
    for i,key in enumerate(('A','B')):
        data=np.load(study/f'audit1/{key}/curves.npz')
        for j,k in enumerate((3,4)):
            ax=axes[i,j]
            for field,label in [('target','Recorded acoustic excess'),('original','Fixed knots C'),('candidate','Adaptive knots C')]:
                power=data[field][k];ax.plot(data['time'],power/max(power.mean(),1e-30),label=label)
            ax.set(title=f'{key}: {[(1200,4500),(4500,14000)][j]} Hz',xlabel='Seconds from fixed crop',ylabel='Power / own mean')
            ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.savefig(out/'curves.png',dpi=140);plt.close(fig)
    paragraphs=[
        '先比较B的固定／自适应控制点，再听A接火和完整启动。所有试听固定乘0.25，无逐条归一化、房间处理或限幅，只有一个播放器。',
        '这一轮用相同数量的幅度控制点描述短促首响，避免固定时间网格把首响拉宽。C的模态、频率和声部容量保持，没有回放原音频。',
        'B最高频的时间误差从约2.64–2.83降到0.45–0.57，A最高频也改善；A中高频略有取舍。图中比较的是各频段除以自身均值后的时间形状，不代表机械音色已经获认可。B弱中高频仍保留原局部包络，不宣称物理声源分离。',
        '完整启动仍是A车外DNA＋F2怠速＋A混合录音启动事件的工程示范，0.58秒拖转和RPM为工程设定。B车内事件保持独立。']
    links=[('A-candidate.parameters.json','A事件参数'),('B-candidate.parameters.json','B事件参数'),
           ('candidate.preset.json','完整候选V12配方'),('candidate.take.json','确定性行程'),('original.preset.json','上轮配方')]
    (out/'index.html').write_text(page('启动事件 · 自适应幅度控制点',paragraphs,tracks,links),encoding='utf-8')
    save(out/'tracks.json',tracks);print(str(out/'index.html'),flush=True)


if __name__=='__main__':main()
