"""Publish coefficient-geometry observations; no audition or runtime promotion."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','known','known-audit','real','real-audit','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_review.py')
    known,real,ka,ra = [load(p/'report.json') for p in (a.known,a.real,a.known_audit,a.real_audit)]
    for study,audit in [(a.known,ka),(a.real,ra)]:
        assert audit['result']=='independent_coefficient_geometry_audit_passed'
        assert audit['producer_report_sha256']==sha(study/'report.json')
        assert audit['max_mean_normalized_moment_error']<=2e-9
    labels=[r['label'] for r in known['cases']]
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    x=np.arange(4)
    for shift,key,label,color in [(-.25,'empirical','Input population','#252525'),
                                  (0,'population_gaussian','Full-covariance Gaussian','#e38b2c'),
                                  (.25,'model_interpolation','Original model + uniform u','#b84042')]:
        y=[r['moments'][key]['power_CV'][0] for r in known['cases']]
        axes[0].bar(x+shift,y,.24,label=label,color=color)
    axes[0].set(xticks=x,xticklabels=labels,ylabel='Coefficient-power CV (std / mean)',ylim=(0,.65),
                title='Same compiler: AM versus constant-magnitude PM')
    axes[0].legend(fontsize=8,loc='upper left')
    for j,row in enumerate(known['cases']):
        for i,render in enumerate(row['renders']):
            y=np.array(render['HF_std_dB']).ravel()
            axes[1].plot(np.full(8,j+(i-1)*.12),y,'o',ms=4,alpha=.7,color=['#336699','#517f4e','#8d4c92'][i],
                         label=f'Seed {render["seed"]}' if j==0 else None)
    axes[1].set(xticks=x,xticklabels=labels,ylabel='Actual C HF band std (dB)',ylim=(0,1.1),
                title='Original C, 4 seconds; final 3 seconds observed')
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('Phase-only input can become amplitude motion after Gaussian closure',fontsize=13)
    fig.text(.5,.015,'Left: distributional coefficient moments. Right: finite waveform-band observations; different units and averaging.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.04,1,.94]);fig.savefig(a.out/'known_geometry.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(3,2,figsize=(12,10),sharey=True)
    ticks=['3-6 L','3-6 R','6-8 L','6-8 R','8-10 L','8-10 R','10-14 L','10-14 R']
    ratios=[];source_cv=[];gaussian_cv=[];model_cv=[];phase_cv=[];amplitude_cv=[];interpolation_effect=[]
    for row,ax in zip(real['cases'],axes.ravel()):
        full,phase,amplitude=[r['moments'] for r in row['variants']]
        for data,key,label,color,style in [(full,'empirical','Observed coefficients','#252525','o-'),
                                         (full,'population_gaussian','Full covariance Gaussian','#e38b2c','s-'),
                                         (full,'model_interpolation','Original model + uniform u','#b84042','^-'),
                                         (phase,'model_interpolation','Phase-only counterfactual','#348e99','x--')]:
            ax.plot(x:=np.arange(8),data[key]['power_CV'],style,label=label,color=color,ms=4,lw=1.2)
        ax.set(title=row['label'].replace('F3 Fifth ','')+f' ({row["variants"][0]["rows"]} coefficient rows)',
               xticks=x,xticklabels=ticks,ylim=(0,.85),ylabel='Coefficient-power CV')
        ax.tick_params(axis='x',labelsize=7,rotation=30);ax.grid(alpha=.2)
        observed=np.array(full['empirical']['power_CV']);g=np.array(full['population_gaussian']['power_CV'])
        m=np.array(full['model_interpolation']['power_CV'])
        ratios.extend((g/observed).tolist());source_cv.extend(observed);gaussian_cv.extend(g);model_cv.extend(m)
        phase_cv.extend(phase['model_interpolation']['power_CV']);amplitude_cv.extend(amplitude['model_interpolation']['power_CV'])
        interpolation_effect.extend(abs(m-np.array(full['model_checkpoint']['power_CV'])))
    handles,legends=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,legends,loc='upper center',bbox_to_anchor=(.5,.963),ncol=2,fontsize=9)
    fig.suptitle('All six frozen F3 anchors: moment mismatch precedes added HF detail',y=.994,fontsize=14)
    fig.text(.5,.01,'Four HF bands in kHz. Phase-only observed CV is zero. Counterfactuals are NOT physical layers or proposed presets.\nFinite training apertures, no held-out timbre claim; coefficient power omits waveform beats/leakage.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.05,1,.91]);fig.savefig(a.out/'F3_geometry.png',dpi=150);plt.close(fig)
    def span(values):
        return [float(min(values)),float(max(values))]
    pm=known['cases'][2]
    stats=dict(known_phase_only_population_CV=pm['moments']['population_gaussian']['power_CV'][0],
               known_phase_only_uniform_interpolation_CV=pm['moments']['model_interpolation']['power_CV'][0],
               known_phase_only_C_HF_std_dB=span([v for r in pm['renders'] for channel in r['HF_std_dB'] for v in channel]),
               F3_observed_CV=span(source_cv),F3_population_Gaussian_CV=span(gaussian_cv),
               F3_original_model_uniform_CV=span(model_cv),F3_population_Gaussian_to_observed_CV_ratio=span(ratios),
               F3_phase_only_original_model_uniform_CV=span(phase_cv),F3_amplitude_only_original_model_uniform_CV=span(amplitude_cv),
               F3_uniform_interpolation_vs_checkpoint_absolute_CV_change=span(interpolation_effect),
               F3_Gaussian_CV_larger_than_observed_coordinates=sum(v>1 for v in ratios),coordinates=len(ratios),
               physical_phase_contribution_fraction_identified=False,electronic_timbre_cause_proven=False,
               replacement_or_new_hearing=False)
    save(a.out/'observations.json',stats)
    save(a.out/'report.json',dict(result='coefficient_geometry_observations_published',observations=stats,
         known_report_sha256=sha(a.known/'report.json'),real_report_sha256=sha(a.real/'report.json'),
         known_audit_report_sha256=sha(a.known_audit/'report.json'),real_audit_report_sha256=sha(a.real_audit/'report.json'),
         images={n:sha(a.out/n) for n in ['known_geometry.png','F3_geometry.png']},
         observations_sha256=sha(a.out/'observations.json'),reviewer_sha256=sha(__file__)))
    print(stats)


if __name__=='__main__':
    main()
