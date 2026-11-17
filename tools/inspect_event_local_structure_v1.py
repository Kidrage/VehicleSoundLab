"""Apply the declared local observer once to unchanged exterior startup material."""
import argparse
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from event_authoring.audio import read
from event_local_structure.spectrum import WINDOWS,observe
from event_local_structure.inspect import inspect
from research_archive_v1 import load,save,sha


def run(repo,out,report):
    root=Path('E:/VehicleSoundLab/references/analysis')
    known=root/'event_local_structure_v1/known1'
    proof=load(known/'report.json');assert proof['result']=='passed'
    for name,digest in proof['source_bindings'].items():assert sha(repo/name)==digest
    bindings=dict(proof['source_bindings'])
    bindings['tools/inspect_event_local_structure_v1.py']=sha(__file__)
    for name,digest in bindings.items():
        dest=out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);assert sha(dest)==digest
    report.update(source_bindings=bindings,known_first_report=str(known/'report.json'),known_first_sha256=sha(known/'report.json'))
    runtime=load(root/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime)==459 and all(sha(repo/name)==digest for name,digest in runtime.items())
    selection=load(repo/'research/A_exterior_startup_v1_selection.json')
    source=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    assert sha(source)==selection['source_sha256']
    display={};spectra={}
    for name,interval in [('crank',selection['early_seconds']),('catch',selection['later_seconds']),('background',selection['background_seconds'])]:
        folder=out/name;folder.mkdir()
        x,rate,binding=read(source,*interval)
        sf.write(folder/'source.wav',x,rate,subtype='DOUBLE')
        case=dict(id=name,source=binding,source_wave_sha256=sha(folder/'source.wav'),observations=[])
        report['cases'].append(case)
        for n in WINDOWS:
            for hop in (n,n//4):
                policy='nonoverlap' if hop==n else 'overlap'
                identity=str(n)+'-'+policy
                result,observed=inspect(x,n,hop)
                path=folder/(identity+'.json');save(path,result)
                np.savez_compressed(folder/(identity+'.npz'),
                    power_LR=observed['power'],complex_center_LR=observed['complex_center'],
                    starts=observed['starts'],hz=observed['hz'])
                case['observations'].append(dict(id=identity,sha256=sha(path),
                    array_sha256=sha(folder/(identity+'.npz')),summaries=result['summaries'],windows=result['windows']))
                display[name,n,policy]=result['summaries']
                if n in (1536,6144) and policy=='overlap':spectra[name,n]=observed
                print(name,identity,'windows',result['windows'],'peaks',sum(len(r['peaks']) for r in result['inventories']),flush=True)
        save(out/'report.json',report)
    # Same full context, solely for visual observation; not another fitting crop.
    context,rate,binding=read(source,*selection['full_reference_seconds'])
    context_obs=observe(context,3072,768)
    np.savez_compressed(out/'context-spectrum.npz',power_LR=context_obs['power'],hz=context_obs['hz'],
        starts=context_obs['starts'],first_source_frame=binding['first_frame'])
    report['context_visual_only']=binding
    fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for col,name in enumerate(('crank','catch','background')):
        for row,n in enumerate((1536,6144)):
            item=spectra[name,n];density=item['power'].mean(axis=-1)/(48000/n)
            db=10*np.log10(np.maximum(density,1e-20))
            ax=axes[row,col]
            view=ax.pcolormesh(item['centres'],item['hz'],db.T,shading='auto',vmin=-105,vmax=-20,cmap='magma')
            ax.set_ylim(60,4500);ax.set_title(name+' / '+str(round(n/48))+'ms native Hann')
            ax.set_xlabel('Seconds within unchanged crop');ax.set_ylabel('Hz')
    fig.colorbar(view,ax=axes,label='Raw mean-channel PSD / dBFS² per Hz',shrink=.8)
    fig.savefig(out/'source-spectra.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,4,figsize=(15,7),layout='constrained')
    styles=[('crank','#b85834','o'),('catch','#237a9a','s'),
        ('off_grid_tones','#444444','^'),('independent_white_noise','#a19b25','x'),
        ('stochastic_resonance','#8256a8','d')]
    for row,band in enumerate((1,3)):
        for col,n in enumerate(WINDOWS):
            ax=axes[row,col]
            for name,color,marker in styles:
                values=[]
                for policy in ('overlap','nonoverlap'):
                    if name in ('crank','catch'):summary=display[name,n,policy][band]
                    else:
                        hop=n//4 if policy=='overlap' else n
                        found=next(v for v in proof['observations'] if v['fixture']==name and v['window_frames']==n and v['hop_frames']==hop)
                        summary=found['summaries'][band]
                    value=summary['phase_resultant_magnitude_LR']
                    values.append(float(np.mean(value)) if value is not None else np.nan)
                ax.plot([0,1],values,color=color,marker=marker,label=name)
            ax.set_xticks([0,1],['75% overlap','No overlap']);ax.set_ylim(0,1.05)
            ax.set_title(str(n/48)+'ms / '+str([(60,300),(300,1200),(1200,4500),(4500,14000)][band])+' Hz')
            ax.set_ylabel('Selected-link phase resultant (descriptive)')
            if col==0 and row==0:ax.legend(fontsize=7)
    fig.savefig(out/'phase-memory.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,4),layout='constrained')
    db=10*np.log10(np.maximum(context_obs['power'].mean(axis=-1)/(48000/3072),1e-20))
    ax.pcolormesh(context_obs['centres']+selection['full_reference_seconds'][0],context_obs['hz'],db.T,
        shading='auto',vmin=-105,vmax=-20,cmap='magma')
    ax.set_ylim(60,4500);ax.set_xlabel('Original A source seconds');ax.set_ylabel('Hz')
    for v in selection['early_seconds']+selection['later_seconds']:
        ax.axvline(v,color='cyan',lw=.7)
    ax.set_title('Unchanged exterior context; boundaries are acoustic selections, not physical ignition timestamps')
    fig.savefig(out/'context.png',dpi=150);plt.close(fig)
    assert all(sha(repo/name)==digest for name,digest in runtime.items())
    report.update(result='passed',runtime_voice_files_unchanged=459,qualified_cases=[],
        no_source_fit_or_generator_promotion=True,
        limitation='Finite selected-peak descriptors, conditioned on local graph uniqueness. Narrow stochastic resonances, overlap, chirp and finite windows confound deterministic oscillator identity. No physical source allocation or RPM inferred.')
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
    print('unchanged exterior source observations complete; no generator candidate or physical class',flush=True)


if __name__=='__main__':main()
