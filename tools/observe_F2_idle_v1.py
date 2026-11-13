"""Measure reviewed F2 raw idle-candidate blocks; no clock, RPM or DNA estimation."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import scipy
from drive_evidence_v1.sources import sha,read
from state_media_v1.measure import recording_measurements,BANDS


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-idle-observation/1',result='running',sources={},real_audio_read=True,
    phase_estimator_run=False,model_exported=False,runtime_changed=False)
try:
    review=load(repo/'research/F_state_audition_v1_review.json')
    assert review['human_listening_result']=='received' and review['short_clip_source_usability_partially_accepted']
    assert review['clip_decisions']['F3_stopped'].startswith('Rejected')
    for path in (Path(__file__),repo/'tools/state_media_v1/measure.py',repo/'tools/drive_evidence_v1/sources.py',
                 repo/'references/segments_v1.json',repo/'research/F_state_audition_v1_review.json'):
        relative=path.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    assert sha(repo/'references/segments_v1.json')==sha(args.workspace/'references/segments_v1.json')
    # Independent raw Fourier/Parseval controls for the reused1s-Hann observation.
    rate=48000
    t=np.arange(2*rate)/rate
    known=.1*np.cos(2*np.pi*31*t)+.4*np.cos(2*np.pi*83*t)+.2*np.cos(2*np.pi*231*t)
    control,arrays=recording_measurements(np.column_stack((known,.8*known)),rate)
    expected=np.array([.1**2/2,(.4**2+.2**2)/2,0,0,0,0,0])
    expected=np.stack((expected,.8**2*expected))
    power_error=float(abs(arrays['band_power_LR'].mean(axis=2)-expected).max())
    window=np.sin(np.pi*np.arange(rate)/rate)**2
    observed=known[:rate]*window
    raw=np.fft.rfft(observed)
    factor=np.full(len(raw),2.);factor[[0,-1]]=1.
    direct_psd=factor*abs(raw)**2/(rate*np.sum(window**2))
    scalar_error=max(float(abs(sum(float(observed[n])*np.exp(-2j*np.pi*k*n/rate) for n in range(rate))-raw[k]))
                     for k in (31,83,231))
    psd_error=float(abs(direct_psd-arrays['mean_psd_LR'][0]).max())
    parseval_error=abs(float(direct_psd.sum())-float(np.sum(observed**2)/np.sum(window**2)))
    assert power_error<=1e-12 and psd_error<=1e-12 and parseval_error<=1e-12 and scalar_error<=1e-9
    report['known_controls']=dict(passed=True,band_power_error=power_error,FFT_psd_error=psd_error,
        scalar_DFT_error=scalar_error,Parseval_error=parseval_error)
    audio,provenance=read(args.workspace,'F2_tailpipe','recording_power')
    assert len(audio)==6*rate
    whole,values=recording_measurements(audio,rate)
    blocks=[];psds=[];powers=[]
    for j in range(3):
        part=audio[j*2*rate:(j+1)*2*rate]
        stats,numeric=recording_measurements(part,rate)
        blocks.append(dict(source_seconds=[6+2*j,8+2*j],recording=stats))
        psds.append(numeric['mean_psd_LR'])
        powers.append(numeric['band_power_LR'].mean(axis=2))
    powers=np.asarray(powers)
    span=10*np.log10(powers.max(axis=0)/powers.min(axis=0))
    np.savez_compressed(args.out/'observations.npz',hz=values['hz'],block_psd=np.asarray(psds),
        block_mean_band_power=powers,whole_mean_psd=values['mean_psd_LR'],whole_audio=audio)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,axes=plt.subplots(2,1,figsize=(10,7),layout='constrained')
    hz=values['hz'];use=(hz>=20)&(hz<=14000)
    for row,psd in zip(blocks,psds):
        axes[0].semilogx(hz[use],10*np.log10(np.maximum(psd[0,use],1e-30)),linewidth=.65,
                        label=str(row['source_seconds'])+'s L')
    axes[0].set(title='F2 near-tailpipe candidate: raw recording spectra, same1s Hann observation',
                xlabel='Frequency / Hz',ylabel='PSD / dBFS per Hz');axes[0].legend(fontsize=8)
    for channel,label in enumerate(('L','R')):
        axes[1].plot(np.arange(len(BANDS)),span[channel],marker='o',label=label)
    axes[1].set(xticks=np.arange(len(BANDS)),xticklabels=[str(lo)+'-'+str(hi) for lo,hi in BANDS],
                xlabel='Recording band / Hz',ylabel='Maximum-minus-minimum over three2s blocks / dB')
    axes[1].legend();figure.savefig(args.out/'F2_idle_blocks.png',dpi=150);plt.close(figure)
    report.update(result='reviewed_F2_recording_blocks_measured_not_idle_DNA_or_RPM',provenance=provenance,
        numeric_libraries=dict(numpy=np.__version__,scipy=scipy.__version__),whole_recording=whole,blocks=blocks,
        three_block_recording_band_span_db_LR=span.tolist(),arrays_sha256=sha(args.out/'observations.npz'),
        plot_sha256=sha(args.out/'F2_idle_blocks.png'),F3_stopped_used=False,
        limits=['Fixed6..12s candidate with user-reported mild wind and moving microphone; recording powers are not physical engine/noise separation',
            'No fundamental-frequency/RPM/phase inference, state profile, measured load or accepted synthesized idle',
            'Three2s block differences do not establish source stationarity or a load-dependent timbre map'])
    print(json.dumps(dict(result=report['result'],band_span_db_LR=span.tolist())),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
