"""Fixed crops around previously inspected D flame frames; no automatic fit."""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from event_authoring.audio import read,sha
from event_authoring.context import probe
from event_authoring.scan import neighborhood
from research_archive_v1 import save,load


def run(out):
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    plan=load(repo/'research/D_flame_probe_v1_plan.json')
    master=load(repo/'references/segments_v1.json')['sources']['D'];source=data/master['master']
    approvals=load(data/'references/approval_manifest.json')
    assert any(r['id']=='D' and r['approved'] for r in approvals)
    assert sha(source)==plan['source_sha256']==master['master_sha256']
    rows=[];values={}
    # Read one fixed encompassing context. All original intervals remain on the
    # source sample lattice; the 36.2s comparison's before-window starts35.85s.
    context,sr,origin=read(source,35.8,46.)
    for group,key in (('visible_flame_frame','visible_flame_frame_seconds'),('comparison_frame','comparison_frame_seconds')):
        for at in plan[key]:
            intervals={name:[at+offset for offset in plan[field]] for name,field in
                [('event','event_offset_seconds'),('before','before_offset_seconds'),('after','after_offset_seconds')]}
            backgrounds={k:intervals[k] for k in ('before','after')}
            report,arrays=probe(source,intervals['event'],backgrounds)
            fixed=neighborhood(context,round(at*sr)-origin['first_frame'])
            for b in report['backgrounds']:
                assert abs(b['full_contrast_db']-fixed['contrast_db'][b['name']])<1e-12
            spectral=[]
            for b,array in zip(report['backgrounds'],arrays):
                f,p,bp,*_=array;df=f[1]-f[0]
                band=[]
                for lo,hi in plan['bands_hz']:
                    mask=(f>=lo)&(f<hi if hi<24000 else f<=hi)
                    ep=float(p[mask].sum()*df);bg=float(bp[mask].sum()*df)
                    band.append(dict(hz=[lo,hi],event_welch_power=ep,background_welch_power=bg,
                        contrast_db=float(10*np.log10(max(ep,1e-30)/max(bg,1e-30)))))
                spectral.append(dict(background=b['name'],bands=band))
            row=dict(frame_seconds=at,frame_class=group,intervals=intervals,probe=report,
                fixed_window_check=fixed,spectral_contrast=spectral)
            rows.append(row)
            name=f'{at:.1f}';values[name+'_frequency']=arrays[0][0];values[name+'_event_psd']=arrays[0][1]
            values[name+'_before_psd']=arrays[0][2];values[name+'_after_psd']=arrays[1][2]
    # Diagnostic graph covers every planned case; there is no ranked-only export.
    fig,axes=plt.subplots(3,1,figsize=(14,10),layout='constrained')
    envelope=np.sqrt(signal.convolve(np.mean(context*context,axis=1),np.ones(48)/48,mode='same'))
    clock=origin['first_frame']/sr+np.arange(len(context))/sr
    axes[0].plot(clock,envelope,lw=.5,color='#385d80');axes[0].set(xlim=(36,46),ylabel='1ms RMS / FS',title='D: original fixed context; lines mark inspected video frames, not acoustic event times')
    for r in rows:axes[0].axvline(r['frame_seconds'],lw=.7,color='#c46833' if r['frame_class']=='visible_flame_frame' else '#729d65',alpha=.7)
    positions=np.arange(len(rows));labels=[str(r['frame_seconds']) for r in rows]
    for index,name in enumerate(('before','after')):
        y=[next(b['full_contrast_db'] for b in r['probe']['backgrounds'] if b['name']==name) for r in rows]
        axes[1].bar(positions+(index-.5)*.34,y,width=.34,label=name)
    axes[1].axhline(3,color='#bd562b',ls='--',lw=.8,label='3dB reference; no physical label')
    axes[1].set(xticks=positions,xticklabels=labels,ylabel='Full-band contrast / dB',xlabel='Source video seek / s; last3 are comparison frames');axes[1].legend()
    # Six-band minimum of the two backgrounds. A positive narrow band is not a
    # full-band event and cannot be promoted from this plot alone.
    matrix=np.array([[min(s['bands'][k]['contrast_db'] for s in r['spectral_contrast']) for r in rows] for k in range(6)])
    mesh=axes[2].imshow(matrix,aspect='auto',origin='lower',vmin=-6,vmax=6,cmap='coolwarm')
    axes[2].set(xticks=positions,xticklabels=labels,yticks=range(6),yticklabels=[f'{lo}..{hi}' for lo,hi in plan['bands_hz']],ylabel='Welch band / Hz',xlabel='Fixed frame / s');fig.colorbar(mesh,ax=axes[2],label='Minimum before/after contrast / dB')
    out.mkdir(parents=True,exist_ok=False);fig.savefig(out/'fixed-probes.png',dpi=140);plt.close(fig)
    np.savez_compressed(out/'spectra.npz',**values)
    exact=out/'exact_sources';exact.mkdir();bindings={}
    for file in (Path(__file__),repo/'research/D_flame_probe_v1_plan.json',repo/'references/segments_v1.json',
                 *sorted((repo/'tools/event_authoring').glob('*.py'))):
        name=file.relative_to(repo).as_posix();target=exact/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(file,target);bindings[name]=sha(file)
    save(out/'report.json',dict(schema='vsl.D-fixed-flame-context-probe/1',result='measured',plan=plan,
        source_sha256=sha(source),rows=rows,both_full_above_3db=[r['frame_seconds'] for r in rows if r['fixed_window_check']['both_full_band_above_3db']],
        source_bindings=bindings,fit_performed=False,physical_identity_confirmed=False,new_timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='measured',rows=len(rows),full_band_contrasts=[dict(seconds=r['frame_seconds'],
        before=r['fixed_window_check']['contrast_db']['before'],after=r['fixed_window_check']['contrast_db']['after']) for r in rows])),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
