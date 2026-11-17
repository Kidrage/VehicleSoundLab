"""Fixed-rule acoustic candidates in approved recordings, not backfire labels."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,default=Path('E:/VehicleSoundLab'))
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal,ndimage
    import soundfile as sf
    from event_authoring.audio import read,sha
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    repo=Path(__file__).resolve().parents[1];a.output.mkdir(parents=True,exist_ok=False)
    cases=[('A_start','A',33,40),('A_rear','A',208,267),('A_moving','A',316,345),
           ('B_start','B',0,45),('B_lift','B',218,230),('B_end','B',810,850),
           ('D_early','D',0,36),('D_late','D',44,59),('E','E',0,124),
           ('F1','F1',0,79),('F2','F2',0,14),('F3','F3',0,278)]
    manifest=json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    approvals={r['id']:r['approved'] for r in json.loads((a.workspace/'references/approval_manifest.json').read_text(encoding='utf-8'))}
    rows=[];fig,axes=plt.subplots(len(cases),1,figsize=(15,25),layout='constrained')
    for (name,identity,start,stop),ax in zip(cases,axes):
        assert approvals[identity]
        path=a.workspace/manifest['sources'][identity]['master']
        with sf.SoundFile(path) as file:stop=min(stop,len(file)/file.samplerate)
        x,sr,provenance=read(path,start,stop)
        f,t,z=signal.stft(x,fs=sr,nperseg=960,noverlap=720,axis=0,boundary=None,padded=False)
        powers=np.stack([(abs(z[(f>=lo)&(f<hi)])**2).sum(axis=0).mean(axis=0) for lo,hi in [(1500,3000),(3000,6000),(6000,10000)]])
        db=10*np.log10(np.maximum(powers,1e-30));delta=db-ndimage.median_filter(db,size=(1,101),mode='nearest')
        score=np.sort(delta,axis=0)[-2]
        peaks,_=signal.find_peaks(score,height=6,distance=20)
        # Retain all candidates, not only the strongest; artifacts/speech remain unclassified.
        events=[dict(source_seconds=float(start+t[k]),two_band_prominence_db=float(score[k]),
            classification='unclassified acoustic transient',source_id=identity) for k in peaks]
        ax.plot(start+t,db.max(axis=0),lw=.7,color='#4b6785')
        for e in events:ax.axvline(e['source_seconds'],color='#c2543b',alpha=.7,lw=.7)
        ax.set(title=f'{name}: approved source {start:g}–{stop:g} s; {len(events)} unclassified candidates',ylabel='HF band dB',xlabel='Original seconds')
        row=dict(name=name,source=provenance,candidates=events)
        rows.append(row)
        np.savez_compressed(a.output/(name+'.npz'),source_seconds=start+t,band_power=powers,prominence=score)
        print(json.dumps(dict(name=name,candidates=events[:15],total=len(events))),flush=True)
    fig.savefig(a.output/'candidates.png',dpi=120);plt.close(fig)
    report=dict(schema='vsl.event-source-inspection/1',recordings=rows,
        detector=dict(window=960,hop=240,local_median_frames=101,two_bands_above_db=6,min_spacing_seconds=.1),
        limits=['Acoustic candidates are not identified exhaust pops, starter parts, shifts or physical event timestamps.',
                'D 36–44 s is excluded: retain the prior zero-candidate experiment without changing its threshold.',
                'No denoising, source separation, sample-rate conversion, independent gain normalization or new media download.'])
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    exact=a.output/'exact_sources';exact.mkdir()
    for path in (Path(__file__),repo/'tools/event_authoring/audio.py'):
        shutil.copy2(path,exact/path.name)
    report['script_sha256']=sha(__file__)
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
