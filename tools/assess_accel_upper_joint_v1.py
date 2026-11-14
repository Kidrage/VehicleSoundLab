"""Summarize all joint upper observations without selecting a passage, lag or new sound."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_assessment.py')
run=load(a.input/'report.json');assert load(a.audit/'report.json')['result']=='passed'
r=dict(result='all_joint_upper_groups_assessed',input_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),segments=[])
fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
for column,segment in enumerate(['F3_fifth1','F3_fifth2','F3_sixth']):
    source=next(v for v in run['observations'] if v['segment']==segment and v['branch']=='original')
    controls=[v for v in run['observations'] if v['segment']==segment and v['branch']!='original'];assert len(controls)==3
    table=[]
    for label,i,j in [('crossband_L',0,2),('crossband_R',1,3),('low_LR',0,1),('high_LR',2,3),('crossband_LR',0,3),('crossband_RL',1,2)]:
        total=source['energy']['normalized_total'][i][j];within=source['energy']['normalized_within'][i][j];between=source['energy']['normalized_between'][i][j]
        whole=source['whole']['normalized_connected'][i][j]
        weighted=sum(v['frames']*v['statistics']['normalized_connected'][i][j] for v in source['tile_moments'])/source['filtered_frames']
        values={key:[v['energy'][key][i][j] for v in controls] for key in ['normalized_total','normalized_within','normalized_between']}
        whole_controls=[v['whole']['normalized_connected'][i][j] for v in controls]
        local_controls=[sum(t['frames']*t['statistics']['normalized_connected'][i][j] for t in v['tile_moments'])/v['filtered_frames'] for v in controls]
        table.append(dict(pair=label,indices=[i,j],total=total,within=within,between=between,
            between_fraction=between/total if total else None,within_fraction=within/total if total else None,
            whole_connected=whole,weighted_tile_connected=weighted,
            phase_controls={k:dict(values=x,range=[min(x),max(x)]) for k,x in values.items()},
            whole_connected_controls=whole_controls,weighted_tile_connected_controls=local_controls))
    r['segments'].append(dict(segment=segment,tiles=source['tiles'],pairs=table))
    ax=axes[0,column]
    for index,pair in enumerate(table[:2]):
        ax.bar(index-.19,pair['within'],width=.35,color='#278d7c',label='Within original 250ms tiles' if index==0 else None)
        ax.bar(index+.19,pair['between'],width=.35,color='#a1824b',label='Between tile means' if index==0 else None)
        lo,hi=pair['phase_controls']['normalized_within']['range'];ax.vlines(index-.19,lo,hi,color='#273b48',lw=4,label='Phase-control within range' if index==0 else None)
    ax.set_xticks([0,1],['L bands','R bands']);ax.set(title=segment,ylabel='Energy covariance / product of means');ax.axhline(0,color='#71828a',lw=.6);ax.legend(fontsize=7)
    ax=axes[1,column];lags=source['energy']['lags_ms']
    for label,i,j,colour in [('L',0,2,'#278d7c'),('R',1,3,'#a1824b')]:
        values=np.array([v['energy']['normalized_lagged'] for v in controls])[:,:,i,j]
        ax.fill_between(lags,values.min(axis=0),values.max(axis=0),color=colour,alpha=.18,label=label+' phase-control range')
        ax.plot(lags,np.array(source['energy']['normalized_lagged'])[:,i,j],'o-',ms=3,color=colour,label=label+' original')
    ax.set(xlabel='Within-tile energy lag (ms)',ylabel='Signed residual energy product / means');ax.axhline(0,color='#71828a',lw=.6);ax.legend(fontsize=7)
for ax in axes.flat:ax.grid(axis='y',alpha=.2)
fig.suptitle('F3 4–8 / 8–14 kHz mixed recordings: slow + fast dependence; no physical source claim',fontsize=12)
file=a.out/'evidence.png';fig.savefig(file,dpi=150);plt.close(fig)
r.update(figure=dict(file=file.name,sha256=sha(file)),all12observations=True,all192tile_moments=True,all11signed_lags=True,
    same_recording_not_independent=True,source_physical_identity=False,new_audio=False,new_profile=False,runtime_changed=False,
    next='Use separate slow colour/level control and jointly generated fast multiband/LR innovations when a full acceleration source is justified. Independent clouds miss observed crossband dependence; one uniform amplitude modulator also cannot be assumed sufficient. Retain band-specific components and source separation limits, validate through native filters before a candidate. New idle candidate remains pending, no duplicate question/promotion.')
save(a.out/'report.json',r)
print(dict(result=r['result'],segments=r['segments']),flush=True)
