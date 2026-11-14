"""Fixed, independent F3 local observations using unchanged acoustic/C kernels."""
import argparse
from fractions import Fraction
import os
from pathlib import Path
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace','out','dna-probe'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):
    os.environ[key]='2'
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from drive_evidence_v1.sources import read
from shift_evidence_v1.spectrum import observe
from B_shift_voice_v1.selection import anchor,track
from decel_source_v1.aperture import extract
from decel_source_v1.checks import run as aperture_controls
from sound_dna.windowed import estimate
from sound_dna.profile import export

a.out.mkdir(parents=True,exist_ok=False)
r = dict(result='running',sources={},inputs={},cases=[],commands=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


try:
    names = ['tools/run_F3_lift_voice_v1.py','research/F3_lift_voice_v1_plan.json',
        'research/F3_lift_context_v1_annotations.json','tools/research_archive_v1.py',
        'tools/drive_evidence_v1/sources.py','tools/drive_evidence_v1/family.py',
        'tools/shift_evidence_v1/spectrum.py','tools/B_shift_voice_v1/selection.py',
        'tools/decel_source_v1/aperture.py','tools/decel_source_v1/checks.py',
        'tools/exterior_clock_v1/warp.py']
    names += [v.relative_to(repo).as_posix() for v in (repo/'tools/sound_dna').glob('*.py')]
    for name in sorted(set(names)):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    plan = load(consume(repo/'research/F3_lift_voice_v1_plan.json'))
    protocol=subprocess.check_output([str(a.dna_probe),'--describe'],cwd=repo,text=True).strip()
    assert protocol=='vsl.sound-dna-raw-export/1',protocol
    r['export_protocol']=protocol
    r['known_apertures_before_source']=aperture_controls(plan)
    # Known family + empty observation controls precede real-waveform reads.
    t=np.arange(2*48000)/48000
    tone=sum(amp*np.cos(2*np.pi*40*k*t+.13*k)
             for k,amp in [(2,.02),(3,.03),(5,.2),(7,.025)])
    obs=observe(np.column_stack([tone,.8*tone]),0,80)
    chosen=anchor(obs,.05)
    family=track(obs,chosen,dict(plan,source_seconds=[0,2]))
    assert family['status']=='connected_observed_family'
    delta=max(abs(v['root_hz']-40) for v in family['rows'])
    assert delta<.1
    empty=observe(np.zeros((48000,2)),0,80)
    missing=track(empty,anchor(empty,.05),dict(plan,source_seconds=[0,1]))
    assert missing['status']=='no_anchor_peak'
    r['known_family_before_source']=dict(root_error_hz=delta,rows=len(family['rows']),silent=missing['status'])
    save(a.out/'report.json',r)
    audio,provenance=read(a.workspace,plan['source'],plan['use'])
    r['source']=provenance
    assert provenance['seconds']==plan['source_seconds']
    consume(a.workspace/'references/segments_v1.json')
    source=load(a.workspace/'references/segments_v1.json')['sources']['F3']
    for key in ('raw','master'):
        consume(a.workspace/source[key])
    sf.write(a.out/'native_context.wav',audio,48000,subtype='FLOAT')
    for case in plan['cases']:
        folder=a.out/case['name'];folder.mkdir()
        first,stop=[round((s-provenance['seconds'][0])*48000) for s in case['seconds']]
        native=audio[first:stop]
        sf.write(folder/'native.wav',native,48000,subtype='FLOAT')
        local=observe(native,case['seconds'][0],plan['window_ms'],hop=plan['hop'])
        np.savez_compressed(folder/'observed.npz',**local)
        selected=anchor(local,case['anchor_seconds'])
        path=track(local,selected,dict(plan,source_seconds=case['seconds']))
        row=dict(case=case,anchor=selected,family=path,qualified=False,renders=[])
        r['cases'].append(row)
        save(folder/'selection.json',row)
        if path['status']!='connected_observed_family':
            row.update(stage='family',reason='Declared local family unsupported; no alternate anchor/window/ref/gate')
            save(a.out/'report.json',r)
            continue
        try:
            normalized,where,info=extract(native,case['seconds'][0],path['rows'],case['center_seconds'],plan)
        except ValueError as exc:
            row.update(stage='aperture',reason=str(exc))
            save(a.out/'report.json',r)
            continue
        sf.write(folder/'normalized.wav',normalized,48000,subtype='FLOAT')
        np.savez_compressed(folder/'coordinates.npz',source_seconds=where)
        frames=len(range(0,len(normalized)-4096+1,256))
        minimum=min(v for values in info['heldout_coherence'].values() for v in values)
        row.update(extraction=info,observations=frames)
        save(folder/'extraction.json',row)
        if frames<plan['gates']['minimum_observations'] or minimum<=plan['gates']['heldout_carrier_coherence']:
            row.update(stage='heldout',reason='Original observation/heldout-carrier gate failed; no profile')
            save(a.out/'report.json',r)
            continue
        model,statistics=estimate(normalized,plan['harmonics'],plan['components'])
        export(folder/'voice.model',model,info['root_hz'])
        ratio=Fraction(46.875/info['root_hz']).limit_denominator(10000)
        reference=signal.resample_poly(normalized,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))
        sf.write(folder/'reference.wav',reference,48000,subtype='FLOAT')
        for seed in plan['seeds']:
            argv=list(map(str,[a.dna_probe,folder/'voice.model',folder/f'DNA_{seed}.wav',plan['seconds'],1,1,seed,512]))
            run=subprocess.run(argv,cwd=repo,capture_output=True,timeout=180)
            (folder/f'C_{seed}.log').write_bytes(run.stdout+run.stderr)
            r['commands'].append(dict(argv=argv,exit_code=run.returncode))
            assert run.returncode==0
            wave,rate=sf.read(folder/f'DNA_{seed}.wav',always_2d=True)
            assert rate==48000 and wave.shape==(plan['seconds']*48000,2) and np.isfinite(wave).all()
            peak=float(abs(wave).max())
            assert peak*.5<plan['gates']['output_peak_after_common_gain']
            row['renders'].append(dict(seed=seed,file=f'DNA_{seed}.wav',frames=len(wave),peak_FS=peak,sha256=sha(folder/f'DNA_{seed}.wav')))
        consume(a.dna_probe)
        row.update(qualified=True,stage='local_voice',statistics=statistics,resample_ratio=[ratio.numerator,ratio.denominator])
        save(a.out/'report.json',r)
        print(dict(name=case['name'],qualified=True,root_hz=info['root_hz'],heldout=info['heldout_coherence']),flush=True)
    r.update(result='fixed_local_cases_checked',qualified=sum(v['qualified'] for v in r['cases']),
        excluded=sum(not v['qualified'] for v in r['cases']),human_accepted=False,runtime_changed=False,
        physical_RPM_or_load=False,room=False,PCM_timeline=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
print(dict(result=r['result'],qualified=r.get('qualified'),excluded=r.get('excluded')))
