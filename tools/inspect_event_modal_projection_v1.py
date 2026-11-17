"""One declared fixed-frequency normalized-capacity study of current startup crops."""
import argparse
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from event_authoring.audio import read
from event_modal_projection.basis import design, training_mask
from event_modal_projection.project import fit, energy
from event_modal_projection.measure import budgets
from research_archive_v1 import load,save,sha


def run(repo,out,report):
    root=Path('E:/VehicleSoundLab/references/analysis')
    known=root/'event_modal_projection_v1/known1'
    verification=load(known/'report.json')
    assert verification['result']=='passed'
    for name,digest in verification['source_bindings'].items():
        assert sha(repo/name)==digest,(name,'Known-first source changed')
    report.update(known_report=str(known/'report.json'),known_report_sha256=sha(known/'report.json'))
    runtime=load(root/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime)==459 and all(sha(repo/name)==digest for name,digest in runtime.items())
    plan=load(repo/'research/event_modal_projection_v1_plan.json')
    bindings=dict(verification['source_bindings'])
    bindings['tools/inspect_event_modal_projection_v1.py']=sha(__file__)
    for name,digest in bindings.items():
        dest=out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        assert sha(dest)==digest
    report['source_bindings']=bindings
    baseline=load(root/'startup_contour_ensemble_v1/baseline1/report.json')
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for column,entry in enumerate(baseline['cases']):
        kind=entry['kind'];folder=out/kind;folder.mkdir()
        original=load(entry['document'])
        assert sha(entry['document'])==entry['document_sha256']
        p=original['parameters'];job=original['source_job']
        source,rate,source_binding=read(job['source'],*job['seconds'])
        background,_,background_binding=read(job['source'],*job['background_seconds'])
        assert source_binding==entry['source'] and background_binding==entry['background']
        assert source_binding['sha256']=='34885942c450127932a25c72a63fdeae59026f30cfe3678a7aba6b1f5f87b964'
        sf.write(folder/'source.wav',source,rate,subtype='DOUBLE')
        sf.write(folder/'background.wav',background,rate,subtype='DOUBLE')
        bgrows,_=budgets(background,np.zeros_like(background),background)
        mask=training_mask(len(source))
        case=dict(kind=kind,document=entry['document'],document_sha256=entry['document_sha256'],
            source=source_binding,background=background_binding,source_wave_sha256=sha(folder/'source.wav'),
            background_mean_band_powers=[r['source'] for r in bgrows],models=[],
            physical_identity_or_RPM_inferred=False)
        report['cases'].append(case)
        plotrows={}
        for model in plan['models']:
            a,spec=design(p['modes'],len(source),model['knots'],model['quadrature'],p['sweep_seconds'])
            result=dict(model)
            for split,selection in [('full',None),('interpolation',mask)]:
                print(kind,model['id'],split,a.shape,'QR begins',flush=True)
                h,r,coeff,fitting=fit(a,source,selection)
                erows={'all':energy(source,h,r)}
                if split=='interpolation':
                    erows.update(train=energy(source,h,r,mask),withheld=energy(source,h,r,~mask))
                brows,arrays=budgets(source,h,r)
                assert fitting['max_normal_residual_FS']<2e-12
                assert max(row['maximum_balance_error_FS2'] for row in brows)<2e-13
                if split=='full':
                    assert abs(erows['all']['signed_cross_FS2'])<2e-13
                    plotrows[model['id']]=arrays
                document=dict(spec,channels=source.shape[1],coefficients=coeff.tolist(),
                    schema='vsl.diagnostic-event-projection/1',runtime_voice=False,
                    source_document_sha256=entry['document_sha256'],source=source_binding,
                    interpolation_probe=split=='interpolation',not_autonomous_generation=True)
                path=folder/(model['id']+'-'+split+'.json')
                save(path,document)
                for label,wave in [('projection',h),('remainder',r)]:
                    sf.write(folder/(model['id']+'-'+split+'-'+label+'.wav'),wave,rate,subtype='DOUBLE')
                result[split]=dict(fitting=fitting,energy=erows,bands=brows,coefficients_sha256=sha(path))
                print(kind,model['id'],split,'SSE explained',erows.get('withheld',erows['all'])['explained_SSE_fraction'],
                    'condition',fitting['condition'],flush=True)
            case['models'].append(result)
            save(out/'report.json',report)
            del a
        # All comparison families have explicitly nested subspaces where expected.
        byid={r['id']:r for r in case['models']}
        for smaller,larger in [('fixed1','quad1'),('fixed1','fixed9'),('quad1','quad5'),('quad5','quad9'),('fixed9','quad9')]:
            assert byid[larger]['full']['energy']['all']['explained_SSE_fraction']+1e-12>=byid[smaller]['full']['energy']['all']['explained_SSE_fraction']
        labels=[r['id'] for r in case['models']];position=np.arange(len(labels))
        ax=axes[0,column]
        ax.bar(position-.16,[r['full']['energy']['all']['explained_SSE_fraction'] for r in case['models']],.32,label='Full-source projection')
        ax.bar(position+.16,[r['interpolation']['energy']['withheld']['explained_SSE_fraction'] for r in case['models']],.32,label='Withheld10ms blocks')
        ax.set_xticks(position,labels);ax.set_title(kind+' / current12 fixed frequencies')
        ax.set_ylabel('Explained native waveform SSE fraction');ax.legend(fontsize=8)
        arrays=plotrows['quad9'];time=(arrays['window_starts']+1024)/48000
        norm=max(arrays['source'][:,2].mean(),1e-30)
        ax=axes[1,column]
        for name,color in [('source','black'),('projection','#28799a'),('remainder','#bd683e'),('cross','#7a5498')]:
            ax.plot(time,arrays[name][:,2]/norm,label=name,color=color,lw=1)
        ax.set_title(kind+' / quad9 /300..1200Hz signed budget')
        ax.set_xlabel('Seconds within unchanged source crop');ax.set_ylabel('Power / mean raw band power');ax.legend(fontsize=8)
    fig.savefig(out/'capacity.png',dpi=150);plt.close(fig)
    assert all(sha(repo/name)==digest for name,digest in runtime.items())
    report.update(result='passed',runtime_voice_files_unchanged=459,qualified_cases=[],
        no_generator_fit_or_runtime_promotion=True,old_random_heldouts_not_used=True,
        source_fit_scope='Conditional same-event acoustic capacity and10ms interpolation; not physical separation, independent-recording validation or autonomous generation')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',cases=[],runtime_integrated=False,goal_complete=False,timbre_accepted=False)
    save(out/'report.json',report)
    try:report=run(Path(__file__).resolve().parents[1],out,report)
    except Exception as error:
        report.update(result='failed',error=repr(error));save(out/'report.json',report)
        raise
    save(out/'report.json',report)
    print('conditional OSC capacity study complete; no candidate promoted',flush=True)


if __name__=='__main__':main()
