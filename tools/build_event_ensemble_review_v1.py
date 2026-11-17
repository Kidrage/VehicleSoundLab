"""Fixed material and actual-C single/ensemble comparisons, with eight paired seeds."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.fit import fit
from event_authoring.native import Renderer,controls
from event_authoring.response_fit import search as single_search,EDGES
from event_authoring.response_ensemble import TRAIN_SEEDS,HELD_OUT_SEEDS,assess,target_powers,band_powers
from event_review import page
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis/event_ensemble_v1')
    assert load(root/'author1/report.json')['result']=='passed'
    native=Renderer(repo);seeds=(*TRAIN_SEEDS,*HELD_OUT_SEEDS);tracks=[];cases=[]
    review=out/'review';review.mkdir();shutil.copy2(__file__,out/'executed_build.py')
    for path in [Path(__file__),*sorted((repo/'tools/event_authoring').glob('*.py'))]:
        dest=out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    fig,axes=plt.subplots(3,1,figsize=(10,9),layout='constrained')
    for ax,name,label in zip(axes,('A_crank','A_catch','B_rank6'),('A 启动早期纹理','A 接火阶段','B 16毫秒短声诊断')):
        job=load(root/'probe1'/name/'source-job.json');source=Path(job['source'])
        x,rate,origin=read(source,*job['seconds']);bg,_,background=read(source,*job['background_seconds'])
        observation,arrays=observe(x,bg);duration=len(x)/rate;targets=target_powers(arrays)
        initial,_=fit(observation,arrays,duration,job.get('gated',False))
        single,old_report=single_search(initial,arrays,duration)
        ensemble=load(root/'probe1'/name/'profile.json');fit_report=load(root/'probe1'/name/'fit.json')
        assert fit_report['qualified']
        save(out/(name+'-single-profile.json'),single)
        save(out/(name+'-ensemble-profile.json'),ensemble)
        save(out/(name+'-single-fit.json'),old_report)
        profiles=dict(single=single,ensemble=ensemble);results={};waveforms={}
        folder=out/name;folder.mkdir();save(folder/'source-job.json',job)
        for variant,profile in profiles.items():
            save(folder/(variant+'-profile.json'),profile)
            # A gated profile has a10s safety limit; the fitted observation is
            # still only this material crop. Exclude release and silence from
            # spectral checks, and evaluate saved FP32 C samples in FP64.
            trials=[];pieces=[];event_frames=len(x)
            length=max(.2,duration+.15);step=round((length+.15)*rate)
            sequence=np.zeros(step*len(seeds))
            for index,seed in enumerate(seeds):
                actual,details=native.render(profile,job['kind'],controls(dict(seed=seed,seconds=length,hold_seconds=duration)))
                powers=band_powers(actual[:event_frames].astype(float));total=float(targets.sum());bands=[]
                for (lo,hi),target,power in zip(EDGES,targets,powers):
                    significant=bool(target>=total*1e-4)
                    error_db=float(10*np.log10(max(power,1e-30)/max(target,1e-30)))
                    passed=abs(error_db)<=3 if significant else power<=max(2*target,2e-4*total)
                    bands.append(dict(hz=[lo,hi],target_power=float(target),generated_power=float(power),
                        significant=significant,error_db=error_db,passed=bool(passed)))
                trials.append(dict(seed=seed,bands=bands,qualified=all(b['passed'] for b in bands)))
                sequence[index*step:index*step+len(actual)]=actual
                sf.write(folder/(variant+'-'+str(seed)+'.wav'),actual,rate,subtype='FLOAT')
            if variant=='ensemble':assert all(t['qualified'] for t in trials)
            results[variant]=trials;waveforms[variant]=sequence
            sf.write(review/(name+'-'+variant+'.wav'),sequence*.25,rate,subtype='FLOAT')
        sf.write(review/(name+'-reference.wav'),x*.25,rate,subtype='FLOAT')
        tracks.append(dict(label=label+' · 原声短参考',file=name+'-reference.wav',
            description='原始混合录音选区，只乘0.25；不是分离后的发动机部件。'))
        for variant,title in [('single','原单次校准'),('ensemble','多次共同校准')]:
            tracks.append(dict(label=label+' · '+title,file=name+'-'+variant+'.wav',
                description='8次实际C独立触发，前4训练／后4独立检查；两版种子、间隔与增益相同。'+
                ('这是未分类短声，不能当成完整回火。' if name.startswith('B') else '这次未接完整车辆状态或替换已有车外启动音。')))
        for offset,(variant,color) in zip((-.12,.12),(('single','#b17a4d'),('ensemble','#426d91'))):
            errors=np.array([[b['error_db'] for b in trial['bands']] for trial in results[variant]])
            significant=targets>=targets.sum()*1e-4;pos=np.arange(6)[significant]+offset
            mean=errors[:,significant].mean(axis=0);lower=errors[:,significant].min(axis=0);upper=errors[:,significant].max(axis=0)
            ax.errorbar(pos,mean,yerr=[mean-lower,upper-mean],fmt='o',capsize=4,color=color,label=variant)
        ax.axhspan(-3,3,alpha=.12,color='green');ax.axhline(0,lw=.8,color='gray')
        ax.set(title=name+' / eight paired actual C triggers',ylabel='Power error / dB',
               xticks=np.arange(6),xticklabels=['0-60','60-300','300-1200','1200-4500','4500-14000','14000-24000'])
        ax.legend();ax.grid(alpha=.2)
        cases.append(dict(name=name,source=origin,background=background,seconds=duration,kind=job['kind'],
            original_single_fit_qualified=old_report['qualified'],single=results['single'],ensemble=results['ensemble'],
            fit_report_sha256=sha(root/'probe1'/name/'fit.json'),physical_identity_confirmed=False))
        print(name,'single',sum(t['qualified'] for t in results['single']),'ensemble',sum(t['qualified'] for t in results['ensemble']),flush=True)
    fig.supxlabel('Frequency band / Hz; dots mean, bars full seed range; weak targets omitted')
    fig.savefig(review/'bands.png',dpi=150);plt.close(fig)
    for row in tracks:
        path=review/row['file'];info=sf.info(path)
        row.update(sha256=sha(path),frames=info.frames,channels=info.channels)
    report=dict(result='passed',tracks=tracks,cases=cases,seeds=list(seeds),monitor_gain=.25,
        author_DLL_sha256=native.identity,goal_complete=False,timbre_accepted=False,
        physical_afterfire_confirmed=False,recording_playback_in_synth=False,vehicle_profile_replaced=False)
    save(out/'report.json',report);save(review/'report.json',report)
    text=page('事件多次触发校准 V1',[
        '这轮处理“同一组参数换随机种子后声线漂移”的问题：4次共同提参，再用另外4次检查。仍是原来的正弦模态与程序噪声共振核，没有新增采样或房间模型。',
        '每组先听原声，再比较单次校准与多次共同校准。合成各有8次独立触发，顺序、间隔、种子和0.25监听增益完全相同，没有逐条响度补偿。原声短参考只播放一次。',
        'A两段来自旧的座舱启动候选，用于验证通用提参方法；它们没有替换当前车外启动方案。B只有16毫秒，仍未确认真实动作，不能把频谱通过当成完成了回火。',
        '图只说明显著频带在8次触发间的功率偏差；绿色为原有±3dB门槛，弱目标频带未画。频谱稳定不等于机械自然度或完整动作已还原。'],tracks,[('report.json','来源／8次C触发记录')],plot='bands.png')
    text=text.replace('原素材与新旧C的高频能量起伏对照','八次C触发的频带功率偏差')
    (review/'index.html').write_text(text,encoding='utf-8')
    print(dict(result='passed',output=str(out)),flush=True)


if __name__=='__main__':main()
