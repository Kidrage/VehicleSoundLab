"""One-player comparison and source-bound stereo/time figures for relative phase."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import urllib.request
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','audio','audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy import signal
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',sources={},inputs={},clips=[],banks=[],wave_statistics=[])
    try:
        study=load(a.study/'report.json');audio=load(a.audio/'report.json');audit=load(a.audit/'report.json')
        assert study['result']=='six_source_relative_phase_evidence_ready' and audio['result']=='relative_phase_paired_audio_ready'
        assert audit['result']=='independent_relative_phase_audio_audit_passed' and audit['producer_sha256']==sha(a.audio/'report.json')
        for path in [a.study/'report.json',a.audio/'report.json',a.audit/'report.json']:report['inputs'][str(path)]=sha(path)
        parent=a.workspace/'baselines/radial_copula_v1'
        assert sha(parent/'manifest.json')==load(repo/'research/radial_copula_v1_summary.json')['manifest_sha256']
        entries={r['path']:r['sha256'] for r in load(parent/'manifest.json')['files']}
        def frozen(name):
            path=parent/name;assert sha(path)==entries[name];report['inputs'][str(path)]=sha(path);return path
        prior=load(frozen('evidence/real2/report.json'))
        geometry=a.workspace/'baselines/coefficient_geometry_v1'
        assert sha(geometry/'manifest.json')==load(repo/'research/coefficient_geometry_v1_summary.json')['manifest_sha256']
        geometry_entries={r['path']:r['sha256'] for r in load(geometry/'manifest.json')['files']}
        cfg=load(repo/'research/relative_phase_v1_audio_plan.json')
        titles=dict(original='原C DNA',fixed_phase='固定相位 · 同幅度对照',relative_phase='左右相位变化')
        bands=[[3000,6000],[6000,8000],[8000,10000],[10000,14000]]
        def wave_stereo(x):
            f,L=signal.welch(x[:,0],48000,nperseg=2048,noverlap=1024)
            _,R=signal.welch(x[:,1],48000,nperseg=2048,noverlap=1024)
            _,cross=signal.csd(x[:,1],x[:,0],48000,nperseg=2048,noverlap=1024)
            values=[]
            for lo,hi in bands:
                mask=(f>=lo)&(f<hi);values.append(cross[mask].sum()/np.sqrt(L[mask].sum()*R[mask].sum()))
            return np.array(values)
        def clip(path,bank,variant,seed,title,note):
            report['inputs'][str(path)]=sha(path);x,rate=sf.read(path,always_2d=True)
            assert rate==48000 and x.shape[1]==2 and np.isfinite(x).all()
            y=x*.5;fade=.5-.5*np.cos(np.pi*np.arange(240)/240)
            y[:240]*=fade[:,None];y[-240:]*=fade[::-1,None]
            key=f'{bank}_{variant}_{seed}';out=a.out/(key+'.wav');sf.write(out,y,48000,subtype='FLOAT')
            assert abs(y).max()<.95
            assert np.array_equal(sf.read(out,always_2d=True)[0],y.astype('float32').astype(float))
            report['clips'].append(dict(key=key,bank_key=bank,variant=variant,seed=seed,title=title,note=note,
                file=out.name,seconds=len(x)/48000,frames=len(x),sha256=sha(out),peak_FS=float(abs(y).max())))
            return wave_stereo(x)
        for i,row in enumerate(audio['cases'],1):
            bank=f'bank{i}';label=row['label'];root=row['root_hz']
            report['banks'].append(dict(key=bank,title=f'五挡第{i}次升速 · 中点',root=root))
            old=next(v for v in prior['cases'] if v['label']==label)
            waves={k:[] for k in titles}
            for j,seed in enumerate(cfg['seeds'],1):
                original=next(v for v in old['audio'] if v['variant']=='original' and v['seed']==seed)
                path=frozen(f'evidence/real2/{label}/{original["file"]}');assert sha(path)==original['sha256']
                waves['original'].append(clip(path,bank,'original',seed,f'{titles["original"]} · 生成{j}','原C统计声源基准；8秒固定音高。'))
                for variant in cfg['variants']:
                    v=next(v for v in row['audio'] if v['variant']==variant and v['seed']==seed)
                    path=a.audio/label/v['file'];assert sha(path)==v['sha256']
                    waves[variant].append(clip(path,bank,variant,seed,f'{titles[variant]} · 生成{j}',
                        f'{titles[variant]}，与另一新版本共享幅度，8秒固定音高。'))
            name=f'evidence/real1/{label}/source.npz';path=geometry/name
            assert sha(path)==geometry_entries[name];report['inputs'][str(path)]=sha(path)
            native=np.load(path)['native'];temp=a.out/(bank+'_native_unscaled.wav');sf.write(temp,native,48000,subtype='FLOAT')
            source=clip(temp,bank,'reference',0,'原声短参考（不循环）','原始短参考保留原音高变化，未与8秒合成对齐。')
            packed=lambda x:np.column_stack([x.real,x.imag]).tolist()
            report['wave_statistics'].append(dict(label=label,source=packed(source),
                variants={k:[packed(x) for x in values] for k,values in waves.items()},
                error_mean={k:np.mean([abs(x-source) for x in values],axis=0).tolist() for k,values in waves.items()}))
        comparison=study['stereo_comparison'];errors=comparison['per_coordinate_errors']
        fig,axes=plt.subplots(1,2,figsize=(13,4.8))
        x=np.arange(6)
        for offset,key,title,color in [(-.25,'old_fixed','Original fixed phases','#6483a5'),(0,'old_absolute','Absolute phase model','#ba795c'),(.25,'relative','Common + relative phase','#347d77')]:
            values=np.array(errors[key]).reshape(6,4).mean(axis=1)
            axes[0].bar(x+offset,values,.24,label=title,color=color)
        axes[0].set(xticks=x,xticklabels=['1 early','1 mid','1 late','2 early','2 mid','2 late'],ylabel='Mean absolute complex-coherence error',title='Six frozen coefficient observations')
        axes[0].legend(fontsize=8)
        improvement=(np.array(errors['old_fixed'])-errors['relative']).reshape(6,4)
        image=axes[1].imshow(improvement,cmap='RdBu',vmin=-.18,vmax=.18,aspect='auto')
        axes[1].set(xticks=range(4),xticklabels=['3–6','6–8','8–10','10–14'],yticks=range(6),yticklabels=['1 early','1 mid','1 late','2 early','2 mid','2 late'],xlabel='Band / kHz',title='Fixed-phase error minus relative-phase error')
        fig.colorbar(image,ax=axes[1],label='Positive improves; negative regresses')
        fig.suptitle('Relative phase improves aggregate stereo evidence; five fixed-phase coordinates regress',fontsize=12)
        fig.tight_layout();fig.savefig(a.out/'stereo_coordinates.png',dpi=150);plt.close(fig)
        fig,axes=plt.subplots(2,2,figsize=(12,7.8))
        labels=['3–6 L','3–6 R','6–8 L','6–8 R','8–10 L','8–10 R','10–14 L','10–14 R']
        for i,(row,observed) in enumerate(zip(audio['cases'],report['wave_statistics'])):
            ax=axes[0,i]
            for variant,title,color in [('original','Original C','#6483a5'),('fixed_phase','Paired fixed','#ba795c'),('relative_phase','Paired relative','#347d77')]:
                ax.plot(range(4),observed['error_mean'][variant],'o-',label=title,color=color,ms=4)
            ax.set(title=row['label'].replace('F3 Fifth ',''),xticks=range(4),xticklabels=['3–6','6–8','8–10','10–14'],ylabel='Actual WAV complex-coherence error',xlabel='Band / kHz');ax.legend(fontsize=8)
            ax=axes[1,i];source=np.diag(np.array(row['source_lag1_power_covariance']))/np.diag(np.array(row['source']['covariance']))
            values=np.array([np.diag(t['lag1_covariance'])/np.diag(t['covariance']) for t in row['temporal']])
            ax.plot(range(8),source,'ko-',ms=3,label='Observed overlapping rows');ax.plot(range(8),values.mean(axis=0),'o-',color='#347d77',ms=3,label='Generated endpoints')
            ax.fill_between(range(8),values.min(axis=0),values.max(axis=0),alpha=.15,color='#347d77')
            ax.set(xticks=range(8),xticklabels=labels,ylabel='Lag1 power product / variance',ylim=(-.2,1.1));ax.tick_params(axis='x',rotation=35,labelsize=8);ax.legend(fontsize=8)
        for ax in axes.ravel():ax.grid(alpha=.2)
        fig.suptitle('Actual waveforms and time law: static coefficient success is not full reconstruction',fontsize=12)
        fig.text(.5,.01,'WAV errors compare 8s fixed-root synthesis to a short changing-root original; Welch2048 / hop1024. Not matched replay or a timbre score.',ha='center',fontsize=8)
        fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(a.out/'wave_time.png',dpi=150);plt.close(fig)
        data=dict(banks=report['banks'],clips=report['clips']);save(a.out/'data.json',data)
        names=['tools/review_relative_phase_v1.py','tools/relative_phase_v1/review.html','tools/check_radial_copula_v1.cjs']
        for name in names:
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);report['sources'][name]=sha(dest)
        template=(repo/'tools/relative_phase_v1/review.html').read_text(encoding='utf-8')
        (a.out/'index.html').write_text(template.replace('__DATA__',(a.out/'data.json').read_text(encoding='utf-8')),encoding='utf-8',newline='\n')
        report['url']='http://127.0.0.1:8789/'+a.out.relative_to(a.workspace).as_posix()+'/index.html'
        for name in ['index.html','data.json','stereo_coordinates.png','wave_time.png']+[c['file'] for c in report['clips']]:
            with urllib.request.urlopen(report['url'].rsplit('/',1)[0]+'/'+name,timeout=15) as response:assert response.read()==(a.out/name).read_bytes()
        report.update(result='relative_phase_one_player_review_ready',heard=False,room=False,widener=False,
            per_clip_normalization=False,images={n:sha(a.out/n) for n in ['stereo_coordinates.png','wave_time.png']})
        save(a.out/'report.json',report);print(dict(result=report['result'],clips=len(report['clips']),url=report['url']))
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
