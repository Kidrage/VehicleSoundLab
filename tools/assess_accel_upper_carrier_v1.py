"""All source carrier spectral/stereo budgets and explicit fixed-OU compatibility results."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','energy','summary','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');energy=load(a.energy/'report.json');summary=load(a.summary/'report.json');audit=load(a.audit/'report.json');assert audit['result']=='passed'
M=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]]);hz=np.arange(6001)*4;select=(hz>=4000)&(hz<14000)
r=dict(result='all12_source_carrier_budgets_assessed_not_voice',input_sha256=sha(a.input/'report.json'),energy_sha256=sha(a.energy/'report.json'),
       summary_sha256=sha(a.summary/'report.json'),audit_sha256=sha(a.audit/'report.json'),cases=[],figures=[])
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained');fig2,ax2=plt.subplots(2,3,figsize=(14,8),layout='constrained')
fig3,ax3=plt.subplots(2,3,figsize=(14,8),layout='constrained')
for row,sr,er in zip(run['observations'],summary['observations'],energy['cases']):
    budgets=[]
    for b in range(4):
        table=sr['summaries'];t=table['target'][b];c=table['Welch_carrier'][b];g=table['Welch_gain'][b];fc=table['Welch_refilter_carrier'][b];fg=table['Welch_refilter_gain'][b]
        budgets.append(dict(band_hz=t['band_hz'],
            repeated_Welch_power_db=(10*np.log10(np.array(c['stereo_power'])/t['stereo_power'])).tolist(),
            gain_only_power_db=(10*np.log10(np.array(g['stereo_power'])/c['stereo_power'])).tolist(),
            refilter_gain_only_power_db=(10*np.log10(np.array(fg['stereo_power'])/fc['stereo_power'])).tolist(),
            carrier_MSC=c['power_weighted_MSC'],gain_MSC=g['power_weighted_MSC'],
            refilter_carrier_MSC=fc['power_weighted_MSC'],refilter_gain_MSC=fg['power_weighted_MSC']))
    with np.load(a.input/row['file']) as f:
        P={key:np.einsum('ai,fij,bj->fab',M,f[key],M)[:,[0,1],[0,1]].real for key in ['target','Welch_carrier','Welch_gain']}
        detail=[]
        for ch in range(2):
            target=P['target'][select,ch];assert np.all(target>0)
            for key in ['Welch_carrier','Welch_gain']:
                values=P[key][select,ch];assert np.all(values>0);error=abs(10*np.log10(values/target))
                detail.append(dict(channel=ch,configuration=key,all4to14k_bins=int(select.sum()),
                    target_power_weighted_absolute_db=float(np.dot(target,error)/target.sum()),maximum_absolute_db=float(error.max())))
    r['cases'].append(dict(segment=row['segment'],branch=row['branch'],gain_fit_available=row['gain_fit_available'],budgets=budgets,
        detailed_spectral_error=detail,energy_compatibility=er,corrected_summaries=sr['summaries']))
    if row['branch']!='original':continue
    column=['F3_fifth1','F3_fifth2','F3_sixth'].index(row['segment'])
    for ch,label in enumerate(['L','R']):
        ax=axes[ch,column]
        for key,name,colour in [('target','Source Welch','#879199'),('Welch_carrier','Gaussian carrier, expected Welch','#247f73'),('Welch_gain','Carrier + fixed joint gain','#365eaa')]:
            ax.plot(hz[select]/1000,10*np.log10(P[key][select,ch]),color=colour,lw=.7,label=name)
        ax.set(title=row['segment']+' | '+label,xlabel='Frequency (kHz)',ylabel='Power density (dB FS^2/Hz)');ax.grid(alpha=.15)
        if ch==column==0:ax.legend(fontsize=7)
    gain=np.array([budgets[b]['gain_only_power_db'] for b in [1,2]]).ravel();ref=np.array([budgets[b]['refilter_gain_only_power_db'] for b in [1,2]]).ravel()
    ax=ax2[0,column];x=np.arange(4);ax.bar(x-.17,gain,width=.32,color='#365eaa',label='Gain vs carrier');ax.bar(x+.17,ref,width=.32,color='#a97a3f',label='Refilter gain vs refilter carrier')
    ax.set_xticks(x,['4-8 L','4-8 R','8-14 L','8-14 R'],rotation=20);ax.set(title=row['segment'],ylabel='Gain-only band power change (dB)');ax.axhline(0,color='#829098',lw=.6);ax.grid(axis='y',alpha=.15)
    if column==0:ax.legend(fontsize=7)
    ax=ax2[1,column]
    for field,label,colour,style in [('carrier_MSC','Carrier','#247f73','o-'),('gain_MSC','Carrier + gain','#365eaa','o-'),
                                    ('refilter_carrier_MSC','Refilter carrier','#aa8054','s--'),('refilter_gain_MSC','Refilter + gain','#7b596c','s--')]:
        ax.plot([0,1],[budgets[b][field] for b in [1,2]],style,color=colour,label=label,ms=4)
    ax.set_xticks([0,1],['4-8 kHz','8-14 kHz']);ax.set(ylabel='Power-weighted stereo MSC');ax.grid(alpha=.15)
    if column==0:ax.legend(fontsize=7)
    with np.load(a.energy/er['file']) as e:
        for rr,(i,j,label) in enumerate([(0,2,'L cross-band'),(1,3,'R cross-band')]):
            ax=ax3[rr,column]
            for key,name,colour in [('target','Source','#247f73'),('previous','Prior white-carrier fit','#879199'),('prediction','Source carrier, same parameters','#365eaa')]:
                ax.plot(np.arange(-5,6)*10,e[key][:,i,j],'o-',color=colour,label=name,ms=3)
            ax.set(title=row['segment']+' | '+label,xlabel='Within-tile lag (ms)',ylabel='Normalized energy covariance');ax.axhline(0,color='#879199',lw=.6);ax.grid(alpha=.15)
            if rr==column==0:ax.legend(fontsize=7)
fig.suptitle('Source-derived Gaussian FIR carrier | all source 4-14 kHz bins\nExact spectral-grid compilation is not waveform or timbre reconstruction',fontsize=12)
fig2.suptitle('Separate gain and diagonal-refilter budgets | fixed source-derived OU parameters\nBand power can remain close while stereo coherence changes',fontsize=12)
fig3.suptitle('Subsequent compatibility diagnostic | carrier changed, OU parameters NOT refitted\nMean spectral matching does not preserve fitted energy statistics automatically',fontsize=12)
for name,figure in [('spectral_shape.png',fig),('power_stereo.png',fig2),('energy_compatibility.png',fig3)]:
    path=a.out/name;figure.savefig(path,dpi=150);plt.close(figure);r['figures'].append(dict(file=name,sha256=sha(path)))
r.update(new_listening_audio=False,new_runtime_profile=False,source_PSD_compiled_not_voice_accepted=True,
    refilter_not_misidentified_as_gain_loss=True,old_Gamma_tau_unchanged=True,no_independent_holdout=True,
    next='Use the source-shaped Gaussian carrier in the same native energy forward fit before any candidate. Preserve 4x4 signs and unavailable controls; update parameters only through the fixed qualified fit, not a blind gain increase. Then qualify actual synthesis/refilter/mix and controllable carrier representation/latency before isolated C. Source firing/state identity and all pending idle/moving35 protections remain.')
save(a.out/'report.json',r)
for row in r['cases']:
    if row['branch']=='original':print(dict(segment=row['segment'],main_budgets=row['budgets'][1:3],detail=row['detailed_spectral_error'],energy_costs=[row['energy_compatibility']['previous_cost'],row['energy_compatibility']['new_cost']]),flush=True)
