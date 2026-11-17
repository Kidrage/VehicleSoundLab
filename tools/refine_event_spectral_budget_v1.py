"""One declared six-band/modal-budget pipeline per existing startup source."""
import argparse
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.contour_all_bands import observations as middle_observations
from event_authoring.contour_ensemble import baseline_errors
from event_authoring.response_ensemble import target_powers
from event_authoring.model import synth
from event_authoring.native import Renderer, controls
from event_spectral_source.profile import TRAIN_SEEDS, HELD_OUT_SEEDS
from event_spectral_source.measure import observations, curves
from event_spectral_source.design import design
from event_spectral_source.fit import solve
from event_spectral_source.voice import render
from refine_startup_band_texture_v1 import assess
from research_archive_v1 import load, save, sha


def run(out, repo, report):
    root=Path('E:/VehicleSoundLab/references/analysis')
    known=root/'event_spectral_budget_v1/known1'
    assert load(known/'report.json')['result']=='passed'
    for p in (repo/'tools/event_spectral_source').glob('*.py'):
        assert sha(p)==sha(known/'exact_sources'/p.relative_to(repo))
    report.update(known_first_report=str(known/'report.json'),known_first_sha256=sha(known/'report.json'))
    sources=[Path(__file__),repo/'research/event_spectral_budget_v1_plan.json',
        repo/'tools/refine_startup_band_texture_v1.py',*sorted((repo/'tools/event_spectral_source').glob('*.py'))]
    for p in sources:
        dest=out/'exact_sources'/p.relative_to(repo)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    renderer=Renderer(repo)
    baseline=load(root/'startup_contour_ensemble_v1/baseline1/report.json')
    fig,axes=plt.subplots(6,2,figsize=(12,15),layout='constrained')
    for column,entry in enumerate(baseline['cases']):
        kind=entry['kind'];folder=out/kind;folder.mkdir()
        original=load(Path(entry['document']))
        assert sha(Path(entry['document']))==entry['document_sha256']
        job=original['source_job']
        x,rate,source=read(job['source'],*job['seconds'])
        bg,_,background=read(job['source'],*job['background_seconds'])
        assert source==entry['source'] and background==entry['background']
        seconds=len(x)/rate
        _,arrays=observe(x,bg)
        time,target=observations(x,bg)
        middle_time,middle,rows=middle_observations(x,bg)
        np.testing.assert_allclose(time,middle_time,atol=1e-15)
        np.testing.assert_allclose(target[1:5],middle,atol=1e-15,rtol=2e-12)
        assert all(r['selected'] for r in rows)
        reference=middle/middle.mean(axis=1)[:,None]
        full_reference=target/np.maximum(target.mean(axis=1),1e-30)[:,None]
        targets=target_powers(arrays)
        designed,budget=design(original['parameters'],arrays,time,target,seconds)
        save(folder/'designed-profile.json',designed)
        legacy=baseline_errors(original['parameters'],reference,seconds,TRAIN_SEEDS)
        print(kind,'one feasibility/conditional-objective pipeline begins',flush=True)
        candidate,fitting=solve(designed,reference,list(range(4)),targets,legacy,seconds)
        path=folder/'candidate-before-validation.json'
        save(path,candidate);save(folder/'training-before-validation.json',fitting)
        digest=sha(path)
        seed_rows,plots=[],{'old_C':[],'candidate_Python':[]}
        for seed in (*TRAIN_SEEDS,*HELD_OUT_SEEDS):
            old,_=renderer.render(original['parameters'],kind,controls(dict(seed=seed,
                seconds=seconds+.15,hold_seconds=seconds)))
            expected=synth(original['parameters'],seed=seed,seconds=seconds+.15,
                release_at=seconds if original['parameters']['gated'] else None)
            expected=np.pad(expected,(0,len(old)-len(expected)))
            c_error=float(np.max(abs(expected-old)));assert c_error<3e-6
            generated=render(candidate,seconds+.15,seed,
                release_at=seconds if original['parameters']['gated'] else None).astype(np.float32)
            om,_=assess(old[:len(x)],targets,reference,[1e30]*4)
            nm,_=assess(generated[:len(x)],targets,reference,om['shape_rmse'])
            om['C_python_error_FS']=c_error
            for label,wave in [('old_C',old),('candidate_Python',generated)]:
                sf.write(folder/(label+'-'+str(seed)+'.wav'),wave,rate,subtype='FLOAT')
                _,power=curves(wave[:len(x)])
                plots[label].append(power/np.maximum(power.mean(axis=1),1e-30)[:,None])
            seed_rows.append(dict(seed=seed,split='training' if seed in TRAIN_SEEDS else 'held_out',
                old=om,candidate=nm,candidate_peak_FS=float(np.max(abs(generated)))))
        assert sha(path)==digest
        old_error=np.array([r['old']['shape_rmse'] for r in seed_rows[:4]])
        new_error=np.array([r['candidate']['shape_rmse'] for r in seed_rows[:4]])
        old_score=np.mean((old_error/np.maximum(old_error,.05))**2)
        new_score=np.mean((new_error/np.maximum(old_error,.05))**2)
        improvement=float((old_score-new_score)/old_score)
        eligible=bool(fitting['phaseI']['feasible'] and improvement>1e-5 and
                      all(r['candidate']['qualified'] for r in seed_rows))
        sf.write(folder/'source-reference.wav',x,rate,subtype='FLOAT')
        save(folder/'original-event-profile.json',original)
        for index,ax in enumerate(axes[:,column]):
            ax.plot(time,full_reference[index],color='black',label='source excess',lw=1.2)
            for label,color in [('old_C','#b95332'),('candidate_Python','#29758d')]:
                values=np.array(plots[label])[:,index]
                ax.plot(time,values.mean(axis=0),color=color,label=label,lw=1)
                ax.fill_between(time,values.min(axis=0),values.max(axis=0),color=color,alpha=.12)
            ax.set_title(kind+' / '+str([(0,60),(60,300),(300,1200),(1200,4500),(4500,14000),(14000,24000)][index])+' Hz')
            ax.set_xlabel('seconds within fixed crop')
            if index==0:ax.legend(fontsize=7)
        report['cases'].append(dict(kind=kind,document=entry['document'],document_sha256=entry['document_sha256'],
            source=source,background=background,observation_frames=len(x),bands=rows,
            initialization=budget,fitting=fitting,seeds=seed_rows,candidate_sha256=digest,
            relative_legacy_shape_improvement=improvement,eligible_for_C_prototype=eligible,
            adopted=False,physical_identity_or_RPM_inferred=False))
        save(out/'report.json',report)
        print(kind,'phaseI',fitting['phaseI']['feasible'],'eligible',eligible,'shape improvement',improvement,flush=True)
    fig.savefig(out/'temporal.png',dpi=150);plt.close(fig)
    runtime=load(root/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime)==459 and all(sha(repo/name)==digest for name,digest in runtime.items())
    report.update(result='passed',runtime_voice_files_unchanged=459,
        qualified_cases=[c['kind'] for c in report['cases'] if c['eligible_for_C_prototype']])
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    report=dict(result='running',cases=[],runtime_integrated=False,goal_complete=False,timbre_accepted=False)
    save(out/'report.json',report)
    try:report=run(out,repo,report)
    except Exception as error:
        report.update(result='failed',error=repr(error));save(out/'report.json',report);raise
    save(out/'report.json',report)
    print('declared full-budget pipelines complete; candidates',report['qualified_cases'],flush=True)


if __name__=='__main__':main()
