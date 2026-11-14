"""Measure fixed approved F3 visible-upshift transient after counterexample controls."""
import argparse
import os
from pathlib import Path
import shutil
import sys
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[name]='2'
import numpy as np
import soundfile as sf
from stereo_transient_v1.features import observe,analyze
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},controls=[])


def consume(path):r['inputs'][str(path)]=sha(path);return path


def execute(name,audio):
    folder=a.out/name;folder.mkdir()
    data=observe(audio,199.5,plan);stats,extra=analyze(data,plan)
    np.savez_compressed(folder/'arrays.npz',audio=audio,**data,**extra)
    save(folder/'result.json',stats)
    print(dict(name=name,dip_db=stats['dip_relative_db'],recovery_db=stats['recovery_rise_db'],qualified=stats['descriptive_broad_dip_recovery']),flush=True)
    return dict(name=name,statistics=stats)


try:
    for name in ['tools/run_F3_shift_transient_v1.py','tools/stereo_transient_v1/features.py',
                 'research/F3_shift_transient_v1_plan.json','research/F3_lift_context_v1_annotations.json','tools/research_archive_v1.py']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    plan=load(consume(repo/'research/F3_shift_transient_v1_plan.json'))
    time=199.5+np.arange(96000)/48000
    phase=.4;left=sum(amp*np.cos(2*np.pi*hz*(time-199.5)) for hz,amp in [(500,.1),(2250,.15),(7000,.2)])
    right=.8*sum(amp*np.cos(2*np.pi*hz*(time-199.5)+phase) for hz,amp in [(500,.1),(2250,.15),(7000,.2)])
    data=observe(np.column_stack([left,right]),199.5,plan)
    errors=[]
    for b,amp in [(2,.1),(4,.15),(6,.2)]:
        expected=np.array([amp**2/2,.8**2*amp**2/2])
        errors.append(float(np.max(abs(data['power'][:,b]-expected))))
        errors.append(float(np.max(abs(data['cross'][:,b]-.8*amp**2/2*np.exp(1j*phase)))))
    assert max(errors)<1e-12
    r['known_stereo_normalization']=dict(maximum_error_FS2=max(errors),cross_convention='conj(L)*R; positive right tone phase -> positive imaginary cross')
    ease=lambda x:np.clip(x,0,1)**2*(3-2*np.clip(x,0,1))
    for seed in [1907,23117,61927,8121907]:
        rng=np.random.default_rng(seed);left=rng.standard_normal(96003);other=rng.standard_normal(96000)
        audio=.04*np.column_stack([left[3:],.65*left[:-3]+np.sqrt(1-.65**2)*other])
        row=execute(f'known_stationary_{seed}',audio);r['controls'].append(row)
        assert not row['statistics']['descriptive_broad_dip_recovery']
        if seed==1907:
            dip=1-.8*(ease((time-200.5)/.02)-ease((time-200.64)/.08))
            row=execute('known_gain_cut',audio*dip[:,None]);r['controls'].append(row)
            assert row['statistics']['descriptive_broad_dip_recovery']
            assert 200.52<=row['statistics']['dip_center_seconds']<=200.66
            monotonic=1-.8*ease((time-200.5)/.2)
            row=execute('known_monotonic_drop',audio*monotonic[:,None]);r['controls'].append(row)
            assert not row['statistics']['descriptive_broad_dip_recovery']
    ratio=1-.2*ease((time-200.5)/.08)
    # Phase is integrated continuously; there is no oscillator reset at pitch change.
    clock=np.cumsum(ratio)/48000
    phases=[2*np.pi*hz*clock for hz in [500,1100,2200,4500,7000]]
    tones=np.column_stack([sum(.02*np.cos(v) for v in phases),sum(.016*np.cos(v+.4) for v in phases)])
    row=execute('known_pitch_fall',tones);r['controls'].append(row)
    assert not row['statistics']['descriptive_broad_dip_recovery']
    save(a.out/'report.json',r)
    parent=a.workspace/'baselines/F3_lift_voice_v1'
    manifest=load(consume(parent/'manifest.json'));path=consume(parent/'evidence/fit2/native_context.wav')
    assert sha(path)==next(v['sha256'] for v in manifest['files'] if v['path']==path.relative_to(parent).as_posix())
    with sf.SoundFile(path) as stream:
        assert stream.samplerate==48000 and stream.channels==2 and len(stream)==288000
        audio=stream.read(96000,always_2d=True,dtype='float64')
    r['source']=execute('source',audio)
    sf.write(a.out/'source_original.wav',audio,48000,subtype='FLOAT')
    annotations=load(consume(repo/'research/F3_lift_context_v1_annotations.json'))
    r.update(result='fixed_F3_transient_measured',source_seconds=[199.5,201.5],
        observed_display_bracket=annotations['transition_brackets'][0],video_frames_reused=25,
        physical_timing_calibrated=False,physical_source_separated=False,runtime_changed=False,
        new_voice=False,new_default=False,new_hearing_acceptance=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
