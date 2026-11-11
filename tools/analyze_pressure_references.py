"""Recorded sub-band stereo level changes; not cylinder/ignition identification."""
from pathlib import Path
import csv
import json
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf
from scipy import signal,ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=ROOT/'references/analysis/pressure_variation_v1'
CASES=[('A_idle','A',208,213),('A_blips','A',237,249),('A_moving','A',316,319.5),('B_cabin','B',218,230)]
BANDS=[(1200,3000),(3000,8000)]


def upstream_evidence():
    path=ROOT/'research/upstream/gen/v10_powertrain.gendsp'
    manifest=json.loads((ROOT/'research/upstream_snapshot.json').read_text())
    assert sha(path)==next(x['sha256'] for x in manifest['files'] if x['path']=='gen/v10_powertrain.gendsp')
    def codes(node):
        if isinstance(node,dict):
            if node.get('maxclass')=='codebox':yield node.get('code','')
            for x in node.values():yield from codes(x)
        elif isinstance(node,list):
            for x in node:yield from codes(x)
    code='\n'.join(codes(json.loads(path.read_text())))
    lines=[x for x in code.splitlines() if x.startswith(('cycle_variation =','bank_fire =','cylinder_l =','cylinder_r =','phase_r ='))]
    assert all(any(x.startswith(key) for x in lines) for key in ['cycle_variation =','bank_fire =','cylinder_l =','cylinder_r =','phase_r ='])
    return dict(revision=manifest['revision'],gen_sha256=sha(path),exact_lines=lines,
        relationship='V6 varies bank frequency and uses separate deterministic bank amplitude rates. Local V09 instead varies pressure waveform arrival/amplitude around a fixed drivetrain crank, retaining common-pin geometry and no root detune.')


def main():
    OUT.mkdir(parents=True,exist_ok=True);fig,axes=plt.subplots(4,1,figsize=(12,10),constrained_layout=True)
    rows=[]
    for (name,identity,start,stop),ax in zip(CASES,axes):
        path=ROOT/f'references/clean/{identity}_decoded_float.wav'
        with sf.SoundFile(path) as f:
            sr=f.samplerate;f.seek(int(start*sr));x=f.read(int((stop-start)*sr),always_2d=True)
        hz,t,z=signal.stft(x,sr,nperseg=2048,noverlap=1808,axis=0,boundary=None,padded=False,scaling='psd')
        power=abs(z)**2 # Frequency, channel, time; channels stay separate.
        levels=[];metrics={}
        for lo,hi in BANDS:
            db=10*np.log10(np.maximum(power[(hz>=lo)&(hz<hi)].sum(axis=0)*2*sr/2048,1e-30))
            change=db-ndimage.uniform_filter1d(db,size=51,axis=-1,mode='nearest')
            inner=change[:,50:-50]
            metrics[f'{lo}_{hi}']=dict(channel_residual_p90_minus_p10_db=(np.percentile(inner,90,axis=1)-np.percentile(inner,10,axis=1)).tolist(),
                residual_lr_correlation=float(np.corrcoef(inner)[0,1]),
                channel_policy='Separate L/R sub-band powers; residual is level minus centered 255 ms moving mean, not separated pressure')
            levels.extend(change)
            ax.plot(t+start,change[0],label=f'{lo}-{hi} L',alpha=.9,lw=.7)
            ax.plot(t+start,change[1],label=f'{lo}-{hi} R',alpha=.7,lw=.7,ls='--')
        ax.set(title=name,xlabel='Original source seconds',ylabel='Local level change dB',ylim=(-18,18));ax.grid(alpha=.2)
        file=OUT/f'{name}.csv'
        with file.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['source_seconds','1200_3000_L_db','1200_3000_R_db','3000_8000_L_db','3000_8000_R_db']);w.writerows(zip(t+start,*levels))
        rows.append(dict(name=name,master=str(path.relative_to(ROOT)).replace('\\','/'),master_sha256=sha(path),source_seconds=[start,stop],metrics=metrics))
    axes[0].legend(ncol=4,fontsize=8);fig.savefig(OUT/'recorded_level_changes.png',dpi=140);plt.close(fig)
    result=dict(schema='vsl.pressure-reference-observations/1',script_sha256=sha(Path(__file__)),recordings=rows,upstream=upstream_evidence(),
        analysis=dict(window_frames=2048,hop_frames=240,window_seconds=2048/48000,level_detrend_seconds=.255,
            warning='42.67 ms support and centered detrending preclude identifying individual firing timing or physical modulation constants.'),
        limits=['Mixed recordings show local level variation but cannot identify COV, pressure timing, phase jitter or independent cylinders.',
            'RPM drift, load changes, camera motion, exhaust/intake/road contributions and recording processing remain confounded.',
            'No new cleaning/gain changes or waveform folding; no source-time controls enter synthesis. Engineering model parameters are not fitted to these statistics.'])
    result['outputs']={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='results.json'}
    (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({r['name']:r['metrics'] for r in rows},indent=2))


if __name__=='__main__':main()
