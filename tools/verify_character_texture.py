"""Independent controls and immutable snapshot for character texture evidence."""
import json
import shutil
from pathlib import Path
from runtime_review import ROOT,sha
from reference_segments import checked_source
from cycle_prediction import phase_grid,predict,band_prediction
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'references/analysis/character_texture_v1'
SNAP=ROOT/'baselines/character_texture_v1'

def controls():
    rate=48000;t=np.arange(4*rate)/rate;times=np.arange(.1,3.9,.002)
    # Counterexample: noiseless additive OSC with a fixed-Hz spectral envelope.
    f=60+20*np.sin(2*np.pi*.7*t)
    phase=2*np.pi*(60*t+20/(2*np.pi*.7)*(1-np.cos(2*np.pi*.7*t)))
    x=np.zeros((len(t),2))
    for n in range(1,121):
        amplitude=.03*np.exp(-((n*f-3870)/160)**2)
        for c in range(2):x[:,c]+=amplitude*np.cos(n*phase+.2*n+.4*c)
    measurements=band_prediction(x,rate,times,60+20*np.sin(2*np.pi*.7*times),
        divisors=(1,),bands=((3000,8000),))
    fixed_hz=measurements[0]
    assert fixed_hz['status']=='measured' and min(fixed_hz['error_to_signal_db_lr'])> -15
    # Known near-Nyquist analytic waveform at the exact returned source times.
    high=np.column_stack((.2*np.cos(2*np.pi*14000*t+.3),-.2*np.cos(2*np.pi*14000*t+.3)))
    grid,meta,inverse=phase_grid(high,rate,times,np.full(len(times),63.7))
    actual=grid.reshape(-1,2);expected=.2*np.cos(2*np.pi*14000*inverse.ravel()+.3)
    error_db=float(10*np.log10(np.mean((actual[:,0]-expected)**2)/np.mean(expected**2)))
    assert error_db< -50,error_db
    assert np.array_equal(actual[:,0],-actual[:,1])
    # A noiseless static harmonic waveform should remain periodic after the
    # same original-Hz analysis filters used for runtime/reference results.
    static=np.column_stack([sum(.03/n*np.cos(2*np.pi*80*n*t+.3*n+.2*c) for n in range(1,101)) for c in range(2)])
    stable=band_prediction(static,rate,times,np.full(len(times),80.),divisors=(1,),bands=((3000,8000),))[0]
    assert max(stable['error_to_signal_db_lr'])< -90,stable['error_to_signal_db_lr']
    return dict(status='pass',fixed_hz_spectral_envelope_noiseless_OSC=fixed_hz,
        counterexample='A noiseless OSC bank with deterministic pitch-dependent coefficients can have poor fixed-template prediction. Error is not a physical noise fraction.',
        static_OSC_with_identical_band_filter=stable,
        analytic_14khz_interpolation_error_db=error_db,anti_phase_channels_preserved_exact=True)

def main():
    if (OUT/'verification.json').exists() or SNAP.exists():raise SystemExit('Preserve completed character_texture_v1 snapshot.')
    data=json.loads((OUT/'results.json').read_text())
    for name,digest in data['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in data['inputs'].items():assert sha(ROOT/name)==digest,name
    old=data['source_results'];assert sha(ROOT/old['path'])==old['sha256']
    primary=data['controls']
    assert max(primary['analytic_chirp']['error_to_signal_db_lr'])< -38
    assert primary['exact_channel_swap'] and primary['gain_invariance'] and not primary['future_template_leakage']
    extra=controls()
    # Explicit category positions avoid misleading line connections when low/
    # high cases contain only the base/combined pair. Keep the original figure.
    tags=['base','pressure','structure','combined']
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
    for case,variants in data['runtime'].items():
        xx=[];yy=[]
        for tag,row in variants.items():
            m=next(v for v in row['cycle_prediction'] if v['band_hz']==[3000,8000] and v['divisor']==5)
            xx.append(tags.index(tag));yy.append(m['error_to_signal_db_lr'][0])
        axes[0].plot(xx,yy,'o-',label=f'{next(iter(variants.values()))["known_engineering_rpm"]} RPM')
    axes[0].set(xticks=range(4),xticklabels=['Base','Pressure\n100%','Structure\n100%','Combined\n65% each'],
        title='C known 720-degree cycle / 3-8 kHz / L',xlabel='Fixed RPM/load; same seed and driving inputs',
        ylabel='Future waveform error / actual power (dB)')
    for label,row in data['references'].items():
        xx=[];yy=[]
        for d in [1,2,5,10]:
            m=next(v for v in row['cycle_prediction'] if v['band_hz']==[3000,8000] and v['divisor']==d)
            if m['status']=='measured':xx.append(d);yy.append(m['error_to_signal_db_lr'][0])
        axes[1].plot(xx,yy,'o-',label=label)
    axes[1].set(xticks=[1,2,5,10],title='A descending passage / 3-8 kHz / L\nUnidentified ridge; different conditions',
        xlabel='Observed-ridge periods per candidate repeat',ylabel='Future waveform error / actual power (dB)')
    for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.savefig(OUT/'cycle_prediction_checked.png',dpi=160);plt.close(fig)
    native=json.loads((ROOT/'renders/v0.16.0/verification.json').read_text())
    for name,digest in native['binaries'].items():assert sha(ROOT/'build-v016/Release'/name)==digest,name
    frozen=json.loads((ROOT/'baselines/v0.16.0/manifest.json').read_text())
    source_count=0
    for item in frozen['files']:
        if item['path'].startswith(('src/','tests/')) or item['path'] in ['CMakeLists.txt','Launch.cmd','Launch-character.cmd','build.ps1','AGENTS.md']:
            assert sha(ROOT/item['path'])==item['sha256'],item['path'];source_count+=1
    history={}
    for folder in sorted((ROOT/'baselines').iterdir()):
        if not (folder/'manifest.json').exists():continue
        manifest=json.loads((folder/'manifest.json').read_text())
        for item in manifest['files']:assert sha(folder/item['path'])==item['sha256'],str(folder/item['path'])
        history[folder.name]=len(manifest['files'])
    assert len(history)==19 and history['v0.16.0']==248
    media={name:checked_source(name) for name in ['A','B']}
    for label,row in data['references'].items():
        for m in row['cycle_prediction']:
            if m['status']=='measured':
                assert m['held_out_cycle_count']>=4
                for fold in m['folds']:assert fold['train_cycle_indices'][1]==fold['test_cycle_indices'][0]
    paths=['tools/cycle_prediction.py','tools/analyze_character_texture.py','tools/verify_character_texture.py',
        'tools/runtime_review.py','tools/reference_segments.py','tools/texture_metrics.py',
        'research/燃烧机械细节效用核查V1.md','research/goal_progress_character_texture_v1.json','README.md']
    a=dict(result='pass',study='character_texture_v1',runtime='0.16.0 unchanged',
        primary_results_sha256=sha(OUT/'results.json'),additional_controls=extra,
        runtime_source_and_contract_files_unchanged=source_count,native_binaries_unchanged=native['binaries'],
        preserved_snapshots=history,approved_media=media,
        source_files={name:sha(ROOT/name) for name in paths},
        artifacts={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        status='Offline evidence only. No noise percentage or perceptual acceptance inferred; full user goal remains active.')
    (OUT/'verification.json').write_text(json.dumps(a,indent=2,allow_nan=False),encoding='utf-8')
    SNAP.mkdir()
    for name in paths:
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for path in OUT.iterdir():
        if path.is_file():
            target=SNAP/'review'/path.name;target.parent.mkdir(exist_ok=True);shutil.copy2(path,target)
    files=[dict(path=str(p.relative_to(SNAP)).replace('\\','/'),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest=dict(study='character_texture_v1',runtime='0.16.0 unchanged',files=files,
        status='Frozen offline character efficacy investigation; no new voicing recipe or subjective acceptance.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for item in files:assert sha(SNAP/item['path'])==item['sha256']
    print(json.dumps(dict(result='pass',files=len(files),preserved_snapshots=len(history),
        fixed_hz_noiseless_OSC_error_db=extra['fixed_hz_spectral_envelope_noiseless_OSC']['error_to_signal_db_lr'],
        interpolation_error_db=extra['analytic_14khz_interpolation_error_db']),indent=2))

if __name__=='__main__':main()
