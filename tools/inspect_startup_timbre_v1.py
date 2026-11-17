"""Measure approved startup recordings against their current actual-C event profiles."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from event_authoring.audio import read,sha
    from event_authoring.measure import spectrum
    from event_authoring.native import Renderer
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    args.output.mkdir(parents=True,exist_ok=False)
    approved=json.loads((data/'references/approval_manifest.json').read_text(encoding='utf-8'))
    assert any(row['id']=='A' and row['approved'] for row in approved)
    manifest=json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    renderer=Renderer(repo);reports=[]
    edges=((0,60),(60,300),(300,1200),(1200,4500),(4500,14000),(14000,24001))
    for kind in ('crank','catch'):
        folder=args.output/kind;folder.mkdir()
        original=data/'references/analysis/event_authoring_v1'/(kind+'2')/'profile.json'
        document=json.loads(original.read_text(encoding='utf-8'));job=document['source_job']
        assert document['provenance']['sha256']==manifest['sources']['A']['master_sha256']
        x,sr,origin=read(job['source'],*job['seconds']);background,_,bg_origin=read(job['source'],*job['background_seconds'])
        assert origin['sha256']==document['provenance']['sha256']
        f,power=spectrum(x);fb,bg=spectrum(background);bg=np.interp(f,fb,bg)
        df=f[1]-f[0];excess=np.maximum(0,power-bg);duration=len(x)/sr
        observed=[float(excess[(f>=lo)&(f<hi)].sum()*df) for lo,hi in edges]
        rows=[];waves=[]
        for seed in (27431,1,20261116,19088743):
            y,render=renderer.render(document['parameters'],kind,dict(seconds=duration,hold_seconds=duration,seed=seed))
            fy,py=spectrum(y[:,None]);generated=[float(py[(fy>=lo)&(fy<hi)].sum()*(fy[1]-fy[0])) for lo,hi in edges]
            rows.append(dict(seed=seed,bands=[dict(hz=[lo,hi],positive_psd_excess_power=target,generated_power=actual,
                error_db=float(10*np.log10(max(actual,1e-30)/max(target,1e-30))))
                for (lo,hi),target,actual in zip(edges,observed,generated)],render=render))
            waves.append(y)
        sf.write(folder/'reference.wav',x*.25,sr,subtype='FLOAT')
        sf.write(folder/'current-C.wav',waves[0]*.25,sr,subtype='FLOAT')
        fig,axes=plt.subplots(2,1,figsize=(10,6),layout='constrained')
        fy,py=spectrum(waves[0][:,None])
        axes[0].semilogx(f[1:],10*np.log10(np.maximum(power[1:],1e-20)),label='Original mean channel power')
        axes[0].semilogx(f[1:],10*np.log10(np.maximum(excess[1:],1e-20)),label='Positive PSD excess')
        axes[0].semilogx(fy[1:],10*np.log10(np.maximum(py[1:],1e-20)),label='Current C seed27431',alpha=.8)
        axes[0].set(xlim=(40,20000),ylim=(-110,-10),ylabel='PSD / dB FS2/Hz',title=kind+' / no level compensation')
        for label,wave in (('Original',x),('Current C',waves[0][:,None])):
            n=(len(wave)//240)*240
            rms=np.sqrt(np.mean(wave[:n].reshape(-1,240,wave.shape[1])**2,axis=(1,2)))
            axes[1].plot((np.arange(len(rms))+.5)*.005,rms,label=label)
        axes[1].set(xlabel='Crop time / s',ylabel='5ms RMS / FS')
        for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.savefig(folder/'diagnosis.png',dpi=140);plt.close(fig)
        shutil.copy2(original,folder/'current-profile.json')
        reports.append(dict(kind=kind,source=origin,background=bg_origin,duration=duration,
            current_profile_sha256=sha(original),seeds=rows,
            limitations=['Positive PSD subtraction is an acoustic observation, not isolated source or a waveform target.',
                        'Six-band errors diagnose existing parameters; no admission gate, new fit, RPM or timbre acceptance.']))
        print(json.dumps(dict(kind=kind,seed27431_band_errors_db=[round(r['error_db'],2) for r in rows[0]['bands']]),ensure_ascii=False),flush=True)
    shutil.copy2(__file__,args.output/'executed_inspection.py')
    (args.output/'report.json').write_text(json.dumps(dict(schema='vsl.startup-timbre-inspection/1',
        cases=reports,renderer_sha256=renderer.identity,monitor_gain=.25,global_bank_changed=False,
        goal_complete=False,timbre_accepted=False),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


if __name__=='__main__':main()
