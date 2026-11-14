"""Publish all extracted curves and an explicit posthoc power-match diagnostic."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(Path(__file__),a.out/'executed_plot.py')
shutil.copy2(repo/'research/idle_cyclic_detail_v1_diagnostic.json',a.out/'diagnostic_plan.json')
r=dict(result='running',input_report_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'))
try:
    assert load(a.audit/'report.json')['result']=='passed'
    report=load(a.input/'report.json');groups={}
    for row in report['observations']:
        with np.load(a.input/row['file']) as f:c=f['covariance']
        groups.setdefault(row['group'],[]).append(c)
    source=np.array(groups['source']);control=np.array(groups['phase_control'])
    old=np.array(groups['static']);new=np.array(groups['relation_full']);lag=np.arange(-96,97)/48
    names=['75 Hz','112 Hz','187 Hz','112 - 75 Hz','187 - 75 Hz','187 - 112 Hz']
    r['groups']={k:len(v) for k,v in groups.items()};r['magnitude_curve_distances']={}
    for name,curves in [('static',old),('relation_full',new)]:
        r['magnitude_curve_distances'][name]={}
        for part,reference in zip(['train','check'],source):
            values=np.sqrt(np.mean((abs(curves)-abs(reference))**2,axis=(1,2,3)))
            r['magnitude_curve_distances'][name][part]=dict(all12=values.tolist(),median=float(np.median(values)))
    r['figures']=[]
    for offset,label in [(0,'native'),(3,'differences')]:
        fig,axes=plt.subplots(4,3,figsize=(16,12),sharex=True,constrained_layout=True)
        for b in range(4):
            for j in range(3):
                k=j+offset;ax=axes[b,j]
                lo,hi=np.min(abs(control[:,:,:,k]),axis=0)[:,b],np.max(abs(control[:,:,:,k]),axis=0)[:,b]
                ax.fill_between(lag,lo,hi,color='#999999',alpha=.25,label='Same-PSD controls: all 6')
                for curves,color,title in [(old,'#b47832','Static: all 12'),(new,'#26936e','Phase-related: all 12')]:
                    v=abs(curves[:,:,b,k]);ax.fill_between(lag,v.min(axis=0),v.max(axis=0),color=color,alpha=.12)
                    ax.plot(lag,np.mean(v,axis=0),color=color,lw=1,label=title)
                ax.plot(lag,abs(source[0,:,b,k]),color='#cf4545',lw=1.5,label='F2 TRAIN')
                ax.plot(lag,abs(source[1,:,b,k]),color='#315baf',lw=1.5,label='F2 CHECK')
                ax.grid(alpha=.18);ax.set_title(f"{report['bands_hz'][b][0]}–{report['bands_hz'][b][1]} Hz | {names[k]}")
                if b==3:ax.set_xlabel('Signed lag (ms)')
                if j==0:ax.set_ylabel('|Normalized cyclic covariance|')
        handles,labels=axes[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,loc='outside lower center',ncols=5,frameon=False)
        fig.suptitle('Idle waveform detail: measured structure, not an audible-quality score',fontsize=16)
        path=a.out/f'{label}.png';fig.savefig(path,dpi=130);plt.close(fig)
        r['figures'].append(dict(file=path.name,sha256=sha(path)))
    # Explicit posthoc diagnostic. This is not a new sound-generating model.
    mean=new.mean(axis=0);denominator=mean[96]
    assert np.min(abs(denominator))>1e-12
    factor=source[0,96]/denominator
    corrected=mean*factor[None,:,:]
    np.savez_compressed(a.out/'zero_match_diagnostic.npz',factor=factor,denominator=denominator,
        generated_mean=mean,corrected_mean=corrected,source=source)
    r['zero_match_diagnostic']=dict(used_for_audio=False,fit_used_check=False,
        minimum_denominator=float(abs(denominator).min()),factor_absmax=float(abs(factor).max()),
        factor_real=factor.real.tolist(),factor_imag=factor.imag.tolist(),
        training_zero_lag_absmax_error=float(abs(corrected[96]-source[0,96]).max()),parts={})
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    for b,ax in enumerate(axes.flat):
        for i,(part,color) in enumerate([('train','#cf4545'),('check','#315baf')]):
            gap=np.sqrt(np.mean(abs(corrected[:,b,:]-source[i,:,b,:])**2,axis=1))
            ax.plot(lag,gap,color=color,label=part.upper())
            r['zero_match_diagnostic']['parts'].setdefault(part,{})[str(b)]=dict(
                complex_rms=float(np.sqrt(np.mean(abs(corrected[:,b,:]-source[i,:,b,:])**2))),
                reference_complex_rms=float(np.sqrt(np.mean(abs(source[i,:,b,:])**2))),
                zero_lag_rms=float(gap[96]))
        ax.set_title(f"{report['bands_hz'][b][0]}–{report['bands_hz'][b][1]} Hz")
        ax.set_xlabel('Signed lag (ms)');ax.set_ylabel('Complex covariance RMS gap');ax.grid(alpha=.2);ax.legend()
    fig.suptitle('Diagnostic only: TRAIN zero-lag matched, no CHECK refit / no audio changes')
    path=a.out/'power_matched_gap.png';fig.savefig(path,dpi=140);plt.close(fig)
    r['figures'].append(dict(file=path.name,sha256=sha(path)))
    r.update(result='published',diagnostic_sha256=sha(a.out/'zero_match_diagnostic.npz'),
        curve_lag_points=193,all32observations_retained=True,no_audio_or_C_change=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],distances=r.get('magnitude_curve_distances'),
    zero_match=r.get('zero_match_diagnostic')),flush=True)
