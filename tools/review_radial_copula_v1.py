"""One-player same-gain radial/phase candidates, source references and honest diagnostics."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import urllib.request
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',clips=[],banks=[],sources={},inputs={})
    try:
        producer=load(a.study/'report.json');audit=load(a.audit/'report.json')
        assert producer['result']=='six_radial_copula_models_and_two_anchor_audio_ready'
        assert audit['result']=='independent_radial_copula_audit_passed' and audit['producer_report_sha256']==sha(a.study/'report.json')
        plan=load(repo/'research/radial_copula_v1_plan.json');cfg=plan['audio']
        prior=load(a.workspace/'baselines/coefficient_geometry_v1/evidence/real1/report.json')
        fig,axes=plt.subplots(3,2,figsize=(12,9),sharey=True)
        labels=['3-6 L','3-6 R','6-8 L','6-8 R','8-10 L','8-10 R','10-14 L','10-14 R']
        rows=[producer['cases'][i] for i in [0,3,1,4,2,5]]
        coherence_errors=[]
        for row,ax in zip(rows,axes.ravel()):
            old=next(r for r in prior['cases'] if r['label']==row['label'])
            new=np.mean([r['joint']['CV'] for r in row['QMC']],axis=0)
            for values,title,color in [(row['source']['CV'],'Observed coefficients','#252525'),
                                       (old['variants'][0]['moments']['model_interpolation']['power_CV'],'Old Gaussian model','#b84042'),
                                       (new,'Positive amplitude quantiles','#347d77')]:
                ax.plot(np.arange(8),values,'o-',ms=3,lw=1.2,label=title,color=color)
            ax.set(title=row['label'].replace('F3 Fifth ',''),xticks=np.arange(8),xticklabels=labels,ylim=(0,.85),ylabel='Coefficient-power CV')
            ax.tick_params(axis='x',rotation=30,labelsize=7);ax.grid(alpha=.2)
            source=np.array(row['source']['complex_coherence'])
            fixed=np.mean([r['fixed']['complex_coherence'] for r in row['QMC']],axis=0)
            joint=np.mean([r['joint']['complex_coherence'] for r in row['QMC']],axis=0)
            coherence_errors.append(dict(label=row['label'],fixed=np.linalg.norm(fixed-source,axis=1).tolist(),
                                         joint=np.linalg.norm(joint-source,axis=1).tolist()))
        handles,legend=axes[0,0].get_legend_handles_labels();fig.legend(handles,legend,loc='upper center',bbox_to_anchor=(.5,.965),ncol=3,fontsize=9)
        fig.suptitle('Training-distribution power motion: positive radial representation',y=.997,fontsize=14)
        fig.text(.5,.01,'Four bands in kHz, three scrambled Sobol ensembles averaged. Coefficient power is NOT native acoustic power or a timbre score.',ha='center',fontsize=8)
        fig.tight_layout(rect=[0,.04,1,.93]);fig.savefig(a.out/'power_CV.png',dpi=150);plt.close(fig)
        fig,axes=plt.subplots(1,3,figsize=(15,4.7))
        x=np.arange(6)
        fixed=np.array([r['fixed'] for r in coherence_errors]);joint=np.array([r['joint'] for r in coherence_errors])
        axes[0].bar(x-.18,np.mean(fixed,axis=1),.35,label='Fixed original phases',color='#567c9d')
        axes[0].bar(x+.18,np.mean(joint,axis=1),.35,label='New phase variation',color='#b47750')
        axes[0].set(title='New phase branch: stereo gap remains',ylabel='Mean absolute complex coherence error',
                    xticks=x,xticklabels=['1 early','2 early','1 mid','2 mid','1 late','2 late']);axes[0].legend(fontsize=8)
        for row,ax in zip([r for r in producer['cases'] if r['audio']],axes[1:]):
            source=np.array(row['source_lag1_power_covariance']).diagonal()/np.diag(np.array(row['source']['covariance']))
            generated=np.array([np.array(t['lag1_covariance']).diagonal()/np.diag(np.array(t['covariance'])) for t in row['temporal']])
            ax.plot(np.arange(8),source,'ko-',label='Observed adjacent rows',ms=3)
            ax.plot(np.arange(8),generated.mean(axis=0),'o-',label='Generated AR / quantile',color='#347d77',ms=3)
            ax.fill_between(np.arange(8),generated.min(axis=0),generated.max(axis=0),color='#347d77',alpha=.15)
            ax.set(title=row['label'].replace('F3 Fifth ',''),ylabel='Lag1 power product / variance',xticks=np.arange(8),xticklabels=labels,ylim=(-.15,1.1))
            ax.tick_params(axis='x',rotation=45,labelsize=7);ax.legend(fontsize=7)
        for ax in axes:ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        fig.suptitle('Joint stereo and time checks: still approximate, not spatial acceptance',fontsize=13)
        fig.text(.5,.01,'Left: four HF bands averaged per anchor. Right: three finite 8s realizations; source rows overlap a four-cycle Hann window.',ha='center',fontsize=8)
        fig.tight_layout(rect=[0,.04,1,.92]);fig.savefig(a.out/'stereo_time.png',dpi=150);plt.close(fig)
        save(a.out/'stereo_gap.json',dict(cases=coherence_errors,mean_fixed_error=float(fixed.mean()),mean_joint_error=float(joint.mean()),
                                         joint_worse_coordinates=int((joint>fixed).sum()),coordinates=24,new_spatial_timbre_accepted=False))
        titles=dict(original='原C DNA',fixed_phase='新幅度 · 固定相位',joint_phase='新幅度＋相位变化（诊断）')
        def clip(path,title,key,bank,variant,seed,note):
            x,rate=sf.read(path,always_2d=True);assert rate==48000 and x.shape[1]==2
            y=x*cfg['listening_gain'];fade=.5-.5*np.cos(np.pi*np.arange(cfg['fade_frames'])/cfg['fade_frames'])
            y[:len(fade)]*=fade[:,None];y[-len(fade):]*=fade[::-1,None]
            peak=float(abs(y).max());assert peak<plan['gates']['listening_peak_FS']
            dest=a.out/(key+'.wav');sf.write(dest,y,48000,subtype='FLOAT')
            saved,sr=sf.read(dest,always_2d=True);assert sr==48000 and np.array_equal(saved,y.astype('float32').astype(float))
            report['inputs'][str(path)]=sha(path)
            report['clips'].append(dict(key=key,bank_key=bank,title=title,variant=variant,seed=seed,note=note,
                file=dest.name,frames=len(saved),seconds=len(saved)/48000,sha256=sha(dest),peak_FS=peak))
        for j,label in enumerate(cfg['anchors'],1):
            row=next(r for r in producer['cases'] if r['label']==label);bank=f'bank{j}'
            report['banks'].append(dict(key=bank,title=f'五挡第{j}次升速 · 中点',root=row['root_hz']))
            for audio in row['audio']:
                assert sha(a.study/label/audio['file'])==audio['sha256']
                seed=cfg['seeds'].index(audio['seed'])+1;key=f'{bank}_{audio["variant"]}_{seed}'
                clip(a.study/label/audio['file'],f'{titles[audio["variant"]]} · 生成{seed}',key,bank,audio['variant'],audio['seed'],
                     f'{titles[audio["variant"]]}，8秒固定音高，生成{seed}。选择后点击播放。')
            raw=a.workspace/f'baselines/coefficient_geometry_v1/evidence/real1/{label}/source.npz'
            native=np.load(raw)['native'];reference=a.out/(bank+'_source_unscaled.wav')
            sf.write(reference,native,48000,subtype='FLOAT')
            report['inputs'][str(raw)]=sha(raw)
            clip(reference,'原声短参考（不循环）',bank+'_reference',bank,'reference',0,
                 '未经清洗／归一化的原始短参考，音高仍随原素材变化；不是8秒合成的时间对齐基准。')
        data=dict(banks=report['banks'],clips=report['clips'])
        save(a.out/'data.json',data)
        template=repo/'tools/radial_copula_v1/review.html'
        (a.out/'index.html').write_text(template.read_text(encoding='utf-8').replace('__DATA__',(a.out/'data.json').read_text(encoding='utf-8')),encoding='utf-8',newline='\n')
        for n in ['tools/review_radial_copula_v1.py','tools/radial_copula_v1/review.html']:
            dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest);report['sources'][n]=sha(dest)
        report['url']='http://127.0.0.1:8789/'+a.out.relative_to(a.workspace).as_posix()+'/index.html'
        for n in ['index.html','data.json','power_CV.png','stereo_time.png','stereo_gap.json']+[r['file'] for r in report['clips']]:
            with urllib.request.urlopen(report['url'].rsplit('/',1)[0]+'/'+n,timeout=15) as response:assert response.read()==(a.out/n).read_bytes()
        report.update(result='radial_copula_one_player_review_ready',producer_report_sha256=sha(a.study/'report.json'),
            audit_report_sha256=sha(a.audit/'report.json'),images={n:sha(a.out/n) for n in ['power_CV.png','stereo_time.png']},
            same_gain=True,per_clip_normalization=False,room=False,heard=False,new_phase_spatial_accepted=False)
    except Exception as exc:
        report.update(result='failed',error=repr(exc));raise
    finally:save(a.out/'report.json',report)
    print(dict(result=report['result'],clips=len(report['clips']),url=report.get('url')))


if __name__=='__main__':main()
