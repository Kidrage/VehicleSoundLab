"""Capture the adopted exterior contours before any multi-realization refinement."""
import argparse
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.temporal_fit import band_curves
from event_authoring.contour_all_bands import observations
from event_authoring.response_ensemble import TRAIN_SEEDS,HELD_OUT_SEEDS,target_powers,band_powers
from event_authoring.model import synth
from event_authoring.native import Renderer,controls
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1')
    original=load(root/'verification5/report.json');assert original['result']=='passed'
    for path in [Path(__file__),repo/'research/startup_contour_ensemble_v1_plan.json',
                 *sorted((repo/'tools/event_authoring').glob('*.py'))]:
        target=out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    native=Renderer(repo);report=dict(result='running',goal_complete=False,timbre_accepted=False)
    try:
        cases=[];fig,axes=plt.subplots(4,2,figsize=(12,11),layout='constrained')
        for column,kind in enumerate(('crank','catch')):
            document_path=Path(original['profiles'][kind]['document']);document=load(document_path)
            folder=out/kind;folder.mkdir();save(folder/'document.json',document)
            job=document['source_job'];x,rate,source=read(job['source'],*job['seconds']);bg,_,background=read(job['source'],*job['background_seconds'])
            sf.write(folder/'original.wav',x,rate,subtype='FLOAT');sf.write(folder/'background.wav',bg,rate,subtype='FLOAT')
            observation,arrays=observe(x,bg);targets=target_powers(arrays);time,target,bands=observations(x,bg)
            shape_reference=target/np.maximum(target.mean(axis=1),1e-30)[:,None]
            rows=[];curves=[]
            for seed in (*TRAIN_SEEDS,*HELD_OUT_SEEDS):
                wave,details=native.render(document['parameters'],kind,controls(dict(seed=seed,seconds=len(x)/rate+.15,hold_seconds=len(x)/rate)))
                expected=synth(document['parameters'],seed=seed,seconds=len(wave)/rate,
                    release_at=len(x)/rate if document['parameters']['gated'] else None)
                expected=np.pad(expected,(0,len(wave)-len(expected)))
                error=float(np.max(abs(wave-expected)));assert error<2e-6
                sf.write(folder/(str(seed)+'.wav'),wave,rate,subtype='FLOAT')
                measured=wave[:len(x)].astype(float);power=band_powers(measured);total=float(targets.sum());checked=[]
                for wanted,actual in zip(targets,power):
                    db=float(10*np.log10(max(actual,1e-30)/max(wanted,1e-30)))
                    good=abs(db)<=3 if wanted>=total*1e-4 else actual<=max(wanted*2,total*2e-4)
                    checked.append(dict(target_power=float(wanted),generated_power=float(actual),error_db=db,passed=bool(good)))
                _,generated=band_curves(measured);normalized=generated/np.maximum(generated.mean(axis=1),1e-30)[:,None]
                errors=np.sqrt(np.mean((normalized-shape_reference)**2,axis=1)).tolist();curves.append(normalized)
                rows.append(dict(seed=seed,C_python_max_error=error,spectral=checked,shape_rmse=errors,
                                 spectral_qualified=all(b['passed'] for b in checked),peak=float(np.max(abs(wave)))))
            curves=np.array(curves)
            for index,(band,ax) in enumerate(zip(bands,axes[:,column])):
                ax.plot(time,shape_reference[index],color='black',lw=1.2,label='Material positive excess')
                ax.plot(time,curves[:,index].mean(axis=0),color='#386e9b',lw=1,label='Current C mean')
                ax.fill_between(time,curves[:,index].min(axis=0),curves[:,index].max(axis=0),color='#386e9b',alpha=.2,label='Eight C range')
                ax.set(title=f'{kind} / {band["hz"][0]}..{band["hz"][1]}Hz / contrast {band["contrast_db"]:.1f}dB',
                       xlabel='Material-local time / s',ylabel='Mean-normalized band power');ax.grid(alpha=.2)
                if index==0:ax.legend(fontsize=8)
            case=dict(kind=kind,document=str(document_path),document_sha256=sha(document_path),
                source=source,background=background,observation_frames=len(x),bands=bands,realizations=rows)
            save(folder/'report.json',case);cases.append(case)
            print(kind,'spectral',sum(r['spectral_qualified'] for r in rows),'/8',flush=True)
        fig.savefig(out/'temporal.png',dpi=150);plt.close(fig)
        report.update(result='passed',cases=cases,actual_C_realizations=16,
            no_fit_performed=True,no_runtime_or_profile_change=True,author_DLL_sha256=native.identity)
    except Exception as error:report.update(result='failed',error=repr(error));raise
    finally:save(out/'report.json',report)
    print(dict(result=report['result'],output=str(out)),flush=True)


if __name__=='__main__':main()
