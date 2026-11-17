"""Approved original audio and neighboring video frames around an event candidate."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


CASES = {
    'A_startup': dict(source='A', seconds=[35.,40.5], frames=[35.+.25*k for k in range(23)],
                    crop=[0.,0.,1.,1.], caption='Cabin startup context / controls and tachometer; no physical source separation'),
    'E_exterior_revs': dict(source='E', seconds=[8.,20.], frames=[8.+.5*k for k in range(25)],
                    crop=[0.,0.,1.,1.], caption='Stationary exterior revs / exhaust-return context; transient identity requires review'),
    'B_catch': dict(source='B', seconds=[15.,25.], frames=[15.+.5*k for k in range(21)],
                    crop=[.30,.34,.58,.59], caption='Startup onset and settling / dashboard; source identity requires context'),
    'A_tailpipe_335': dict(source='A', seconds=[334.6,336.2], frames=[334.8+.1*k for k in range(13)],
                    crop=[0.,0.,1.,1.], caption='Tailpipe recording; unclassified short acoustic increment'),
    'B_start': dict(source='B', seconds=[8.5,17.], frames=[9.+.5*k for k in range(16)],
                    crop=[.27,.04,.77,.48], caption='Startup controls / dashboard; event identity unconfirmed'),
    'F3_103': dict(source='F3', seconds=[101.5,105.5], frames=[102.4+.2*k for k in range(11)],
                    crop=[.16,.05,.56,.49], caption='Cabin driving transient; do not assume afterfire'),
}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--data-root',type=Path,default=Path('E:/VehicleSoundLab'))
    p.add_argument('--case',action='append',choices=CASES)
    p.add_argument('--spec',type=Path,help='Explicit approved-source case map; preserves the default cases when omitted')
    p.add_argument('--ffmpeg',default='D:/repo/tools/ffmpeg/bin/ffmpeg.exe');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);sys.path.insert(0,str(a.data_root/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy import signal
    from PIL import Image,ImageDraw,ImageFont
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from event_authoring.audio import read,sha
    repo=Path(__file__).resolve().parents[1]
    manifest=json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    approved={r['id']:r['approved'] for r in json.loads((a.data_root/'references/approval_manifest.json').read_text(encoding='utf-8'))}
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17);reports=[]
    cases=CASES if a.spec is None else json.loads(a.spec.read_text(encoding='utf-8-sig'))
    if not isinstance(cases,dict) or not cases:raise ValueError('Expected a nonempty timeline case map')
    for name,spec in cases.items():
        if a.case and name not in a.case:continue
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name):raise ValueError('Invalid case name')
        if not isinstance(spec,dict) or not all(k in spec for k in ('source','seconds','frames','crop','caption')):
            raise ValueError('Incomplete timeline specification')
        if (len(spec['seconds'])!=2 or not np.isfinite(spec['seconds']).all() or
            not 0<=spec['seconds'][0]<spec['seconds'][1] or not spec['frames'] or
            len(spec['frames'])>60 or not np.isfinite(spec['frames']).all() or
            not all(spec['seconds'][0]<=v<=spec['seconds'][1] for v in spec['frames']) or
            len(spec['crop'])!=4 or not np.isfinite(spec['crop']).all() or
            not 0<=spec['crop'][0]<spec['crop'][2]<=1 or not 0<=spec['crop'][1]<spec['crop'][3]<=1):
            raise ValueError('Invalid timeline intervals, frames or crop')
        identity=spec['source'];assert approved[identity]
        source=manifest['sources'][identity];audio=a.data_root/source['master'];video=a.data_root/source['video']
        assert sha(audio)==source['master_sha256'] and sha(video)==source['video_sha256']
        folder=a.output/name;folder.mkdir();(folder/'frames').mkdir()
        x,sr,provenance=read(audio,*spec['seconds'])
        sf.write(folder/'original.wav',x,sr,subtype='FLOAT');sf.write(folder/'monitor.wav',x*.25,sr,subtype='FLOAT')
        offset=.036291667 if identity=='B' else 0.
        commands=[]
        def frame(item):
            index,at=item;path=folder/'frames'/f'{index:03}.png'
            command=[a.ffmpeg,'-hide_banner','-loglevel','error','-ss',str(at+offset),'-i',str(video),'-frames:v','1','-y',str(path)]
            subprocess.run(command,check=True,capture_output=True,text=True)
            return dict(source_audio_seconds=at,requested_video_seek_seconds=at+offset,file=str(path.relative_to(folder)),sha256=sha(path),command=command)
        with ThreadPoolExecutor(max_workers=3) as executor:frames=list(executor.map(frame,enumerate(spec['frames'])))
        columns=4;lines=(len(frames)+columns-1)//columns
        sheet=Image.new('RGB',(1600,lines*260),'#f2f4f7');draw=ImageDraw.Draw(sheet)
        for index,row in enumerate(frames):
            original=Image.open(folder/row['file']).convert('RGB');w,h=original.size
            image=original.crop(tuple(round(v*(w if k%2==0 else h)) for k,v in enumerate(spec['crop'])))
            image.thumbnail((388,224));left=6+(index%columns)*400;top=6+(index//columns)*260
            sheet.paste(image,(left,top));draw.text((left,top+228),f"{identity} | audio {row['source_audio_seconds']:.3f}s",font=font,fill='#172338')
        sheet.save(folder/'dashboard.jpg')
        f,t,z=signal.stft(x,fs=sr,nperseg=960,noverlap=720,axis=0,boundary=None,padded=False)
        power=(abs(z)**2).mean(axis=1);bands=[(30,100),(100,300),(300,1200),(1200,4500),(4500,14000)]
        curves=np.stack([power[(f>=lo)&(f<hi)].sum(axis=0)*2/1.5 for lo,hi in bands])
        fig,axes=plt.subplots(3,1,figsize=(13,8),layout='constrained',sharex=True)
        clock=spec['seconds'][0]+np.arange(len(x))/sr
        axes[0].plot(clock[::8],x[::8,0],lw=.4,label='Original channel 1');axes[0].set(ylabel='Original FS',title=name+' | '+spec['caption'])
        for (lo,hi),curve in zip(bands,curves):axes[1].plot(spec['seconds'][0]+t,10*np.log10(np.maximum(curve,1e-30)),lw=.8,label=f'{lo}–{hi} Hz')
        axes[1].legend(ncol=3,fontsize=8);axes[1].set(ylabel='Mean-channel power dB')
        hz,tt,zz=signal.stft(x[:,0],fs=sr,nperseg=2048,noverlap=1568,boundary=None,padded=False)
        image=axes[2].pcolormesh(spec['seconds'][0]+tt,hz,20*np.log10(np.maximum(abs(zz),1e-8)),vmin=-90,vmax=-20,rasterized=True,shading='auto',cmap='magma')
        axes[2].set(ylim=(30,10000),yscale='log',ylabel='Hz (channel 1)',xlabel='Original decoded-audio seconds')
        fig.colorbar(image,ax=axes[2],label='STFT magnitude dBFS')
        fig.savefig(folder/'timeline.png',dpi=130);plt.close(fig)
        np.savez_compressed(folder/'measurements.npz',source_seconds=spec['seconds'][0]+t,band_power=curves,band_edges=bands)
        report=dict(name=name,specification=spec,source=provenance,video_sha256=source['video_sha256'],frames=frames,
            monitor_gain=.25,physical_identity_confirmed=False,
            limits=['Frames show requested nearby seeks, not calibrated ECU or combustion timestamps.',
                'Dashboard crops are only visual context; no automatic OCR or physical RPM claim.',
                'Band powers average channel powers; no cancellation-prone stereo fold or source separation.',
                'No cleaning, fitting, new download or change to the global event bank.'])
        (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');reports.append(report)
        print(name,flush=True)
    exact=a.output/'exact_sources';exact.mkdir()
    for path in (Path(__file__),repo/'tools/event_authoring/audio.py'):shutil.copy2(path,exact/path.name)
    (a.output/'report.json').write_text(json.dumps(dict(schema='vsl.event-timeline-inspection/1',cases=reports),ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
