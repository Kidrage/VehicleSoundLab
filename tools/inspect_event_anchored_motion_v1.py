"""Declared anchored source support and sparse moving-carrier capacity, no refit hunt."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from event_anchored_motion.track import follow
from event_anchored_motion.motion import from_points,design
from event_modal_projection.project import fit,energy
from event_modal_projection.measure import budgets
from research_archive_v1 import load,save,sha


def run(repo,out,report):
    root=Path('E:/VehicleSoundLab/references/analysis')
    known=root/'event_anchored_motion_v1/known1'
    proof=load(known/'report.json');assert proof['result']=='passed'
    bindings=dict(proof['source_bindings'])
    bindings.update({name:sha(repo/name) for name in ['tools/inspect_event_anchored_motion_v1.py',
        'tools/event_modal_projection/measure.py','tools/native_projection_v1/budget.py']})
    for name,digest in bindings.items():
        assert sha(repo/name)==digest
        dest=out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);assert sha(dest)==digest
    prior=root/'event_local_structure_v1/source1'
    observed=load(prior/'report.json');assert observed['result']=='passed'
    assert load(root/'event_local_structure_v1/audit1/report.json')['result']=='passed'
    plan=load(repo/'research/event_anchored_motion_v1_plan.json')
    report.update(source_bindings=bindings,known_first_report=str(known/'report.json'),
        known_first_sha256=sha(known/'report.json'),frozen_inventory_report=str(prior/'report.json'),
        frozen_inventory_report_sha256=sha(prior/'report.json'))
    runtime=load(root/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime)==459 and all(sha(repo/name)==digest for name,digest in runtime.items())
    fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    for row,caseplan in enumerate(plan['source_cases']):
        name=caseplan['id'];folder=out/name;folder.mkdir()
        old=next(c for c in observed['cases'] if c['id']==name)
        assert old['source']['source_seconds']==caseplan['seconds']
        assert old['source']['sha256']=='34885942c450127932a25c72a63fdeae59026f30cfe3678a7aba6b1f5f87b964'
        assert sha(old['source']['path'])==old['source']['sha256']
        source,rate=sf.read(prior/name/'source.wav',always_2d=True)
        assert rate==48000 and sha(prior/name/'source.wav')==old['source_wave_sha256']
        case=dict(id=name,source=old['source'],resolutions=[],projections=[])
        report['cases'].append(case)
        for col,n in enumerate((1536,3072)):
            identity=str(n)
            inputpath=prior/name/(identity+'-overlap.json')
            item=next(v for v in old['observations'] if v['id']==identity+'-overlap')
            assert sha(inputpath)==item['sha256']
            inventory=load(inputpath)
            settings=dict(anchor_seconds=caseplan['anchor_seconds_within_crop'],
                anchor_hz=caseplan['anchor_hz'],band_hz=caseplan['band_hz'])
            support=follow(inventory['inventories'],inventory['frequency_bin_hz'],**settings)
            path=folder/(identity+'.json')
            save(path,dict(settings=settings,tracking=support,inventory_document=str(inputpath),
                inventory_sha256=sha(inputpath),physical_identity_or_RPM=False))
            case['resolutions'].append(dict(id=identity,sha256=sha(path),status=support['status'],
                points=len(support['points']),terminations=support.get('terminations',[])))
            arrays=np.load(prior/name/(identity+'-overlap.npz'))
            assert sha(prior/name/(identity+'-overlap.npz'))==item['array_sha256']
            power=arrays['power_LR'].mean(axis=-1)/(48000/n)
            times=(arrays['starts']+n/2)/48000
            ax=axes[row,col]
            ax.pcolormesh(times,arrays['hz'],10*np.log10(np.maximum(power,1e-20)).T,
                shading='auto',cmap='magma',vmin=-100,vmax=-20)
            ax.set_ylim(*caseplan['band_hz']);ax.set_xlim(0,len(source)/48000)
            ax.plot(settings['anchor_seconds'],settings['anchor_hz'],'wo',mfc='none',ms=8,label='Declared anchor')
            points=support['points']
            if points:ax.plot([p['centre_seconds'] for p in points],[p['hz'] for p in points],color='cyan',lw=1.4,label='Unique contiguous component')
            ax.set_title(name+' / '+str(n/48)+'ms / '+support['status']+' / n='+str(len(points)))
            ax.set_xlabel('Seconds within unchanged source crop');ax.set_ylabel('Acoustic frequency / Hz')
            ax.legend(fontsize=7)
            print(name,n,support['status'],len(points),support.get('terminations'),flush=True)
            span=points[-1]['centre_seconds']-points[0]['centre_seconds'] if points else 0.
            if len(points)<5 or span<.128:
                case['resolutions'][-1]['capacity_probe']='skipped_insufficient_contiguous_support'
                continue
            profile=from_points(points)
            first=round(points[0]['centre_seconds']*48000);frames=round(profile['duration_seconds']*48000)
            x=source[first:first+frames]
            destination=folder/identity;destination.mkdir()
            sf.write(destination/'source.wav',x,48000,subtype='DOUBLE')
            fixed=deepcopy(profile)
            frequency=np.array(profile['frequencies_hz']);seconds=np.array(profile['seconds'])
            average=float(np.sum(.5*(frequency[1:]+frequency[:-1])*np.diff(seconds))/seconds[-1])
            fixed.update(seconds=[0.,profile['duration_seconds']],frequencies_hz=[average,average])
            diagnostic=dict(first_source_frame=old['source']['first_frame']+first,
                observation_frames=frames,source_wave_sha256=sha(destination/'source.wav'),
                scope='Exact same local native samples for moving/fixed carriers; conditional capacity only, not autonomous generation or timbre qualification',models=[])
            for kind,motion in [('fixed',fixed),('moving',profile)]:
                for knots in (1,5):
                    label=kind+str(knots)
                    a,times=design(motion,frames,knots)
                    h,r,c,fitting=fit(a,x)
                    rows,_=budgets(x,h,r)
                    score=energy(x,h,r)
                    assert fitting['max_normal_residual_FS']<2e-12
                    for suffix,wave in [('projection',h),('remainder',r)]:
                        sf.write(destination/(label+'-'+suffix+'.wav'),wave,48000,subtype='DOUBLE')
                    diagnostic['models'].append(dict(id=label,profile=motion,amplitude_knots=knots,
                        amplitude_knot_seconds=times.tolist(),coefficients=c.tolist(),fitting=fitting,
                        energy=score,bands=rows,physical_identity_qualified=False))
                    print(name,n,label,'conditional SSE reduction',score['explained_SSE_fraction'],flush=True)
            save(destination/'projection.json',diagnostic)
            case['projections'].append(dict(id=identity,sha256=sha(destination/'projection.json'),
                local_support_seconds=[points[0]['centre_seconds'],points[-1]['centre_seconds']],
                frames=frames,models=[dict(id=m['id'],explained_SSE_fraction=m['energy']['explained_SSE_fraction']) for m in diagnostic['models']]))
        if len(case['resolutions'])==2:
            tracks=[load(folder/(item['id']+'.json'))['tracking']['points'] for item in case['resolutions']]
            if all(tracks):
                lo=max(v[0]['centre_seconds'] for v in tracks);hi=min(v[-1]['centre_seconds'] for v in tracks)
                if hi>lo:
                    t=np.array([p['centre_seconds'] for p in tracks[0] if lo<=p['centre_seconds']<=hi])
                    one=np.interp(t,[p['centre_seconds'] for p in tracks[0]],[p['hz'] for p in tracks[0]])
                    two=np.interp(t,[p['centre_seconds'] for p in tracks[1]],[p['hz'] for p in tracks[1]])
                    case['cross_resolution']=dict(common_seconds=[lo,hi],comparisons=len(t),
                        frequency_disagreement_RMS_hz=float(np.sqrt(np.mean((one-two)**2))),
                        limitation='Same-recording overlapping observations; descriptive agreement, not independent physical accuracy or long-term phase evidence')
                else:case['cross_resolution']=dict(status='no_positive_common_support')
            else:case['cross_resolution']=dict(status='missing_component')
        save(out/'report.json',report)
    fig.savefig(out/'anchored-support.png',dpi=150);plt.close(fig)
    assert all(sha(repo/name)==digest for name,digest in runtime.items())
    report.update(result='passed',runtime_voice_files_unchanged=459,qualified_cases=[],
        no_new_autonomous_voice_or_runtime_promotion=True,
        limitation='Sparse source-conditioned moving frequency support and projection capacity. No original spectral/temporal generator gate or human listening acceptance claimed; these are not full-event candidates.')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',cases=[],goal_complete=False,timbre_accepted=False,runtime_integrated=False)
    save(out/'report.json',report)
    try:report=run(Path(__file__).resolve().parents[1],out,report)
    except Exception as error:
        report.update(result='failed',error=repr(error));save(out/'report.json',report);raise
    save(out/'report.json',report)
    print('declared support and conditional sparse-carrier capacity finished; no candidate promoted',flush=True)


if __name__=='__main__':main()
