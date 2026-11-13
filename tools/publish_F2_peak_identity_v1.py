"""Plot discrete observation ambiguity and the single omitted37Hz counterfactual."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha


def load(path):return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-peak-identity-review/1',result='running',sources={},real_audio_read=False,
    model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_peak_identity_v1';actual=load(root/'observe1/report.json');audit=load(root/'audit1/report.json')
    assert audit['actual_report_sha256']==sha(root/'observe1/report.json')
    assert audit['result']=='all_graph_edges_ambiguities_and_two_counterfactual_fits_independently_audited'
    prior=load(args.workspace/'references/analysis/F2_local_chirps_v1/observe1/report.json')
    arrays=np.load(root/'observe1/counterfactual.npz');rate=48000;hann=np.sin(np.pi*np.arange(rate)/rate)**2
    fig,axes=plt.subplots(3,1,figsize=(11,11),layout='constrained')
    colors=['#275b91','#d45b28'];labels=['6.0-7.0 s','6.5-7.5 s']
    for row,c,label in zip(prior['observations'][:2],colors,labels):
        peaks=row['measured']['candidates'][4][0];values={p['native_bin_Hz']:p['power'] for p in peaks}
        keys=sorted(k for k in values if 30<=k<=55)
        axes[0].scatter(keys,[10*np.log10(values[k]) for k in keys],color=c,label=label)
        for k in (37,44 if row is prior['observations'][0] else 45):
            rank=next(i+1 for i,p in enumerate(peaks) if p['native_bin_Hz']==k)
            axes[0].annotate(f'{k} Hz: rank {rank}',(k,10*np.log10(values[k])),xytext=(5,9),textcoords='offset points',color=c)
    axes[0].set(title='Amplitude rank changes; the 37 Hz peak remains observed',ylabel='Native Hann FFT peak power (dB, common scale)',xlabel='Native frequency (Hz)',ylim=(22,49))
    axes[0].legend();axes[0].grid(alpha=.2)
    channel=actual['channels'][0];centers=np.mean(np.array(actual['source_windows']),axis=1)
    for i,row in enumerate(channel['frames']):
        nodes=[n for n in row if 30<=n['frequency_Hz']<=48]
        for n in nodes:
            unresolved=n['predecessor']=='ambiguous';axes[1].scatter(centers[i],n['frequency_Hz'],
                color='#999999' if unresolved else '#275b91',marker='x' if unresolved else 'o',s=35)
        if i:
            old=channel['frames'][i-1]
            for g in channel['transitions'][i-1]['components']:
                if g['unique']:
                    a=old[g['previous'][0]];b=row[g['current'][0]]
                    if 30<=a['frequency_Hz']<=48 and 30<=b['frequency_Hz']<=48:
                        axes[1].plot(centers[i-1:i+1],[a['frequency_Hz'],b['frequency_Hz']],color='#275b91',ls=':',lw=1)
    axes[1].set(title='Discrete correspondence: blue = unique link; gray x = ambiguous predecessor',
        xlabel='Source-window center (s); dotted edges are NOT phase trajectories',ylabel='Native frequency (Hz)',ylim=(29,49))
    axes[1].grid(alpha=.2)
    freq=np.fft.rfftfreq(rate,1/rate)
    for key,c,label in [('audio','#333333','Raw source'),('before','#d45b28','Residual: original 5 lines'),('after','#275b91','Residual: add observed 37 Hz')]:
        values=arrays['audio'][:,0] if key=='audio' else arrays['audio'][:,0]-arrays[key][:,0]
        spectrum=abs(np.fft.rfft(hann*values))/hann.sum()
        axes[2].plot(freq,20*np.log10(np.maximum(spectrum,1e-12)),color=c,label=label)
    axes[2].set(xlim=(30,55),ylim=(-100,-25),xlabel='Native frequency (Hz)',ylabel='Hann projection amplitude (dBFS)',
        title='6.5-7.5 s exploratory fit: 37 Hz residual -95.94%; overall cost -3.93%')
    axes[2].legend();axes[2].grid(alpha=.2)
    fig.suptitle('F2 idle source observations only: main chirp bounds STILL fail; no new DNA',fontsize=14)
    target=args.out/'F2_peak_identity.png';fig.savefig(target,dpi=150);plt.close(fig)
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);dest=args.out/'exact_sources'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);report['sources'][relative.as_posix()]=sha(path)
    report.update(result='discrete_peak_correspondence_and_counterfactual_plotted',plot_sha256=sha(target),
        input_report_sha256=sha(root/'observe1/report.json'),audit_report_sha256=sha(root/'audit1/report.json'),
        limits=['Left channel shown; both channel observations audited, not independent acoustic trials',
            'Every native peak retained without amplitude threshold; graph ambiguity is intentional',
            'No audio rendered or improved naturalness inferred from residual reduction'])
    print(json.dumps(dict(result=report['result'],plot=str(target))),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
