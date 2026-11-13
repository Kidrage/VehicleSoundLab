"""Plot every native window, including failed fits and broken correspondences."""
import argparse,json,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
(a.out/'executed_publish.py').write_bytes(Path(__file__).read_bytes())
plan=load(a.input/'exact_sources/research/low_chirp_v1_plan.json');report=load(a.input/'report.json')
fig,axes=plt.subplots(3,1,figsize=(12,11),constrained_layout=True)
known=next(r for r in report['controls']['cases'] if r['id']=='moving_plus_fixed')['correspondence']
for track in known['tracks']:
    x=np.array(track['windows'])*.25+.25
    axes[0].plot(x,track['frequencies_hz'],'o-',color='#087f8c' if track['classification']=='locally_moving' else '#925c00',lw=1.5,ms=4)
axes[0].set_title('Known mixture: 3 moving + 3 fixed lines; all 6 tracked through 7 windows')
axes[0].set_ylabel('Frequency (Hz)');axes[0].set_xlabel('Known signal time (s)');axes[0].set_ylim(30,305)
band_reports=[]
for ax,spec in zip(axes[1:],plan['real_sources']):
    folder=a.input/spec['id'];windows=load(folder/'windows.json');links=load(folder/'correspondence.json')
    path=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1'/spec['id']/'training.wav'
    audio,rate=sf.read(path,always_2d=True);n=plan['frames'];hann=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    hz=np.fft.rfftfreq(n,1/rate);mask=(hz>=30)&(hz<300);cells=[];powers=[]
    for i,window in enumerate(windows):
        start=window['start_frame'];raw=audio[start:start+n];state=dict(np.load(folder/f'window{i}.npz'))
        source_fft=np.fft.rfft(raw*hann[:,None],axis=0)
        residual_fft=np.fft.rfft(state['residual']*hann[:,None],axis=0)
        cells.append(np.sum(abs(source_fft[mask])**2,axis=1))
        row=dict(window=i,success=window['success'],in_sample_residual_power_ratio={})
        for lo,hi in [(30,120),(120,300)]:
            ix=(hz>=lo)&(hz<hi)
            row['in_sample_residual_power_ratio'][f'{lo}-{hi}']=(np.sum(abs(residual_fft[ix])**2,axis=0)/np.sum(abs(source_fft[ix])**2,axis=0)).tolist()
        powers.append(row)
    cells=np.asarray(cells).T;db=10*np.log10(np.maximum(cells,1e-30)/cells.max())
    start,end=spec['seconds'];ax.imshow(db,origin='lower',aspect='auto',cmap='Greys',vmin=-40,vmax=0,
        interpolation='nearest',extent=[start+.125,end-.125,29,299])
    for w in windows:
        x=w['source_center_seconds']
        if not w['success']:ax.axvspan(x-.12,x+.12,color='#c9312c',alpha=.09)
        for row in w['lines']:
            ax.scatter(x,row['frequency_hz'],s=15 if row['eligible'] else 11,
                c='#00a59c' if row['eligible'] else '#cf534a',marker='o' if row['eligible'] else 'x')
    for track in links['tracks']:
        if len(track['windows'])>1:
            x=[windows[i]['source_center_seconds'] for i in track['windows']]
            ax.plot(x,track['frequencies_hz'],color='#00a59c',lw=1.)
    ax.set_title(f'{spec["id"]}: green=conditional local support, red=excluded; no track reaches 5 windows')
    ax.set_ylabel('Frequency (Hz)');ax.set_xlabel('Original source time (s)');ax.set_ylim(30,300)
    band_reports.append(dict(source=spec['id'],windows=powers,
        note='In-sample reconstruction residual only; not independent validation or physical layer power.'))
for ax in axes:ax.grid(alpha=.15)
fig.savefig(a.out/'local_tracks.png',dpi=160);plt.close(fig)
save(a.out/'report.json',dict(result='all_known_and_real_tracks_plotted',
    parent_sha256=sha(a.input/'report.json'),band_reports=band_reports,holdout_read=False,
    plot_sha256=sha(a.out/'local_tracks.png'),listening_acceptance=False))
print(json.dumps(dict(result='plotted',image=str(a.out/'local_tracks.png'))))
