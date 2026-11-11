"""Build stationary A exterior anchors; preserve camera context and clock provenance."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--probe',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read,sha
from drive_evidence_v1.family import follow
from exterior_clock_v1.warp import warp,polish,carrier_rows
from sound_dna.windowed import estimate
from sound_dna.profile import export

repository=Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True,exist_ok=False)
audio,provenance=read(args.workspace,'A_exterior_blips','exterior_dynamic_observation')
source=args.workspace/'references/analysis/drive_evidence_v1/observed/A_exterior_blips/audio.npz'
frozen=json.loads((args.workspace/'baselines/drive_evidence_v1/manifest.json').read_text(encoding='utf-8'))
bound=next(row for row in frozen['external_payloads'] if row['path']==source.relative_to(args.workspace).as_posix())
assert sha(source)==bound['sha256']
with np.load(source) as data:
    hz=data['hz'];times=data['seconds'];power=data['psd_LR'].mean(axis=0)
paths={}
for name,start,stop,anchor,reference in [('fall',238.1,239.35,64,5),('idle_context',243.5,247.8,10,10)]:
    checks=tuple(m for m in (2,3,5,7,10,15,20) if m!=reference)
    selected=follow(hz,times,power,start,stop,anchor,reference,checks,16,(8,90))
    assert selected['status']=='connected_observed_family'
    paths[name]=selected
report=dict(schema='vsl.exterior-anchor-build/1',source=provenance,paths=paths,
    accepted=False,probe_sha256=sha(args.probe),anchors=[],observation_sha256=sha(source),
    scope='One stationary rear camera238..248s; never mixed with accepted moving close-tailpipe DNA/LF',
    limits=['Acoustic roots, not independently measured RPM/load',
        'Falling-rev windows include varying RPM and exhaust transfer; no per-state/load atlas yet',
        'Low-root model represents only its first288harmonics; unresolved/inharmonic and higher noise remain separate work',
        'Fixed-mean-phase OSC models unaccepted; no physical intake/exhaust/road separation'])
cases=[('A Stationary Low','idle_context',243.6,247.5,10),
    ('A Stationary Lower Mid','fall',238.75,239.30,5),
    ('A Stationary Upper Mid','fall',238.33,238.73,5),
    ('A Stationary High','fall',238.10,238.37,5)]
for name,path_key,start,stop,reference in cases:
    output=args.out/name;output.mkdir()
    rows=paths[path_key]['rows']
    clock_times=np.array([row['seconds'] for row in rows]);root=np.array([row['root_hz'] for row in rows])
    original,positions,initial=warp(audio,provenance['seconds'][0],clock_times,root,start,stop)
    y,where,phase=polish(audio,provenance['seconds'][0],original,positions,reference,initial['source_cutoff_hz'])
    base=phase['root_hz_median']
    sf.write(output/'normalized_before_float.wav',original,48000,subtype='FLOAT')
    sf.write(output/'normalized_float.wav',y,48000,subtype='FLOAT')
    np.savez_compressed(output/'coordinates.npz',source_seconds=where,initial_source_seconds=positions)
    diagnostics={}
    for order in (3,5,7,10,15,20):
        _,before=carrier_rows(original,order);_,after=carrier_rows(y,order)
        def describe(z):
            return dict(mean_magnitude=np.mean(abs(z),axis=0).tolist(),
                coherence=(abs(z.mean(axis=0))/np.maximum(np.mean(abs(z),axis=0),1e-30)).tolist())
        diagnostics[str(order)]=dict(fitted_reference=order==reference,before=describe(before),after=describe(after))
    model,stats=estimate(y,harmonics=288,components=12)
    assert 288*base*1.1<21600
    export(output/'voice.model',model,base)
    np.savez_compressed(output/'statistics.npz',**model)
    ratio=Fraction(46.875/base).limit_denominator(10000)
    fixed=signal.resample_poly(y,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))
    sf.write(output/'fixed_reference_float.wav',fixed,48000,subtype='FLOAT')
    rendered=[]
    for pitch in (.9,1.,1.1):
        raw=output/f'raw_{pitch:.1f}.wav'
        command=[str(args.probe),str(output/'voice.model'),str(raw),'8',str(pitch),'1','1']
        result=subprocess.run(command,check=True,capture_output=True,timeout=90)
        generated,rate=sf.read(raw,always_2d=True)
        assert rate==48000 and generated.shape==(8*48000,2) and np.isfinite(generated).all()
        assert not np.array_equal(generated[:4*48000],generated[4*48000:])
        rendered.append(dict(pitch=pitch,peak=float(abs(generated).max()),sha256=sha(raw),command=command,
            stdout=result.stdout.decode('utf-8',errors='replace')))
    # Compare signal spectra at the same restored acoustic root, before any
    # listening gain. No Eq, normalization, room or per-variant RMS matching.
    generated,_=sf.read(output/'raw_1.0.wav',always_2d=True)
    def psd(x):return signal.welch(x[240:-240],fs=48000,nperseg=min(8192,len(x)-480),axis=0,detrend=False)
    fr,pr=psd(fixed);fg,pg=psd(generated)
    bands={}
    for lo,hi in [(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,14000)]:
        ref=pr[(fr>=lo)&(fr<hi)].sum(axis=0)*(fr[1]-fr[0])
        gen=pg[(fg>=lo)&(fg<hi)].sum(axis=0)*(fg[1]-fg[0])
        bands[f'{lo}_{hi}']=dict(reference_db=(10*np.log10(ref+1e-30)).tolist(),
            generated_minus_reference_db=(10*np.log10((gen+1e-30)/(ref+1e-30))).tolist())
    fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained')
    ax.semilogx(fr,10*np.log10(pr.mean(axis=1)+1e-30),label='Warped recording at anchor root',lw=1)
    ax.semilogx(fg,10*np.log10(pg.mean(axis=1)+1e-30),label='C sustained OSC',lw=1,alpha=.85)
    ax.axvline(288*base,color='#555555',ls='--',lw=.8,label='288th harmonic')
    ax.set(xlim=(28,14000),ylim=(-140,-10),xlabel='Hz',ylabel='PSD dBFS/Hz',title=name+' | no level matching')
    ax.legend(fontsize=8);ax.grid(alpha=.2);fig.savefig(output/'spectrum.png',dpi=140);plt.close(fig)
    record=dict(name=name,base_hz=base,model_sha256=sha(output/'voice.model'),
        original_warp=initial,phase_polish=phase,carrier_diagnostics=diagnostics,statistics=stats,
        modeled_top_hz=288*base,render=rendered,bands=bands,
        source_rpm_label=None,reference_policy='Restored acoustic root; no recorded snippet loops in generated files')
    (output/'build.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    report['anchors'].append(record)
    print(name,'base',round(base,5),'root span',phase['inferred_root_hz_range'],'raw peak',rendered[1]['peak'],flush=True)
report['source_sha256']={str(p.relative_to(repository)).replace('\\','/'):sha(p)
    for p in [Path(__file__),repository/'tools/drive_evidence_v1/family.py',
        *repository.joinpath('tools/exterior_clock_v1').glob('*.py'),
        *repository.joinpath('tools/sound_dna').glob('*.py')]}
(args.out/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Four stationary-context anchors compiled and rendered by unchanged C sound_dna.')
