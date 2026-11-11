"""Ingest user-approved D/E with unchanged stereo and indexed video frames.
No denoise, normalization, EQ, mono conversion, RPM inference or fitting.
"""
import hashlib
import json
import subprocess
from datetime import datetime,timezone
from fractions import Fraction
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf
from PIL import Image,ImageDraw,ImageFont
OUT=ROOT/'references/analysis/DE_usability_v1'
FFMPEG=r'D:\repo\tools\ffmpeg\bin\ffmpeg.exe'
FFPROBE=r'D:\repo\tools\ffmpeg\bin\ffprobe.exe'
def run(args):return subprocess.run(list(map(str,args)),cwd=ROOT,check=True,capture_output=True,timeout=120)
def probe(path,args):return json.loads(run([FFPROBE,'-v','error',*args,'-of','json',path]).stdout)
def overview(folder,frames,name):
    w,h=400,248;columns=4;rows=(len(frames)+columns-1)//columns
    board=Image.new('RGB',(w*columns,h*rows),(18,28,35));draw=ImageDraw.Draw(board)
    font=ImageFont.truetype(r'C:\Windows\Fonts\consola.ttf',15)
    for i,row in enumerate(frames):
        with Image.open(folder/row['file']) as im:
            im.thumbnail((400,225));x=(i%columns)*w;y=(i//columns)*h
            board.paste(im,(x,y));draw.text((x+7,y+225),f"{name}  n={row['index']}  PTS={row['pts_seconds']:.6f}s",font=font,fill=(230,240,240))
    board.save(folder/'overview.jpg',quality=94)
def main():
    if OUT.exists():raise SystemExit('Preserve DE_usability_v1; use a new analysis version.')
    OUT.mkdir(parents=True)
    approved=json.loads((ROOT/'references/approval_manifest.json').read_text(encoding='utf-8'))
    result=dict(created_utc=datetime.now(timezone.utc).isoformat(),sources={},
        processing='Native-rate, unchanged stereo float32 decode; no filters or gain. Frame PTS are not independently measured A/V synchronization.')
    for identity in ['D','E']:
        authorization=next(x for x in approved if x['id']==identity);assert authorization['approved']
        provenance=json.loads((ROOT/f'references/raw/{identity}_provenance_v1.json').read_text(encoding='utf-8'))
        raw=ROOT/provenance['raw_file'];assert sha(raw)==provenance['sha256']
        folder=OUT/identity;folder.mkdir()
        streams=probe(raw,['-show_streams','-show_format'])
        (folder/'streams.json').write_text(json.dumps(streams,indent=2),encoding='utf-8')
        audio=next(x for x in streams['streams'] if x['codec_type']=='audio')
        video=next(x for x in streams['streams'] if x['codec_type']=='video')
        assert audio['channels']==2
        master=ROOT/f'references/clean/{identity}_decoded_float.wav'
        if master.exists():raise FileExistsError(master)
        decode=[FFMPEG,'-nostdin','-v','error','-n','-i',raw,'-map','0:a:0','-vn','-c:a','pcm_f32le',master]
        run(decode);x,rate=sf.read(master,always_2d=True,dtype='float64')
        assert rate==int(audio['sample_rate']) and sf.info(master).subtype=='FLOAT' and x.shape[1]==2 and np.isfinite(x).all()
        rms=np.sqrt(np.mean(x*x,axis=0));peak=np.max(abs(x),axis=0)
        block=round(rate*.1);powers=np.array([np.mean(x[i:i+block]**2,axis=0) for i in range(0,len(x)-block+1,block)])
        fullframes=probe(raw,['-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp,best_effort_timestamp_time'])['frames']
        timebase=Fraction(video['time_base']);times=np.array([int(f['best_effort_timestamp'])*float(timebase) for f in fullframes])
        assert len(times)>0 and np.all(np.diff(times)>0)
        indices=sorted(set(int(np.argmin(abs(times-t))) for t in np.arange(0,float(times[-1]),4 if identity=='D' else 6)))
        indices.append(len(times)-1);indices=sorted(set(indices))
        expression='+'.join(f'eq(n,{i})' for i in indices)
        extract=[FFMPEG,'-nostdin','-v','error','-n','-i',raw,'-map','0:v:0','-vf',f"select='{expression}'",'-fps_mode','passthrough',folder/'frame_%03d.png']
        run(extract);frames=[]
        for count,index in enumerate(indices,1):
            path=folder/f'frame_{count:03d}.png';assert path.is_file()
            frames.append(dict(index=index,pts=int(fullframes[index]['best_effort_timestamp']),
                time_base=str(timebase),pts_seconds=float(times[index]),file=path.name,sha256=sha(path)))
        (folder/'video_frames.json').write_text(json.dumps(dict(frame_count=len(times),time_base=str(timebase),
            first_pts=int(fullframes[0]['best_effort_timestamp']),last_pts=int(fullframes[-1]['best_effort_timestamp']),
            selected=frames,all_frames=fullframes),indent=2),encoding='utf-8')
        overview(folder,frames,identity)
        stats=dict(sample_rate=rate,frames=len(x),channels=2,seconds=len(x)/rate,
            rms_dbfs=(20*np.log10(np.maximum(rms,1e-30))).tolist(),peak=peak.tolist(),
            samples_abs_ge_0999=np.sum(abs(x)>=.999,axis=0).tolist(),samples_abs_ge_1=np.sum(abs(x)>=1,axis=0).tolist(),
            sample_correlation=float(np.corrcoef(x.T)[0,1]),
            power100ms_percentile_dbfs=np.percentile(10*np.log10(np.maximum(powers,1e-30)),[5,50,95],axis=0).tolist(),
            note='No music/speech/source-isolation/AGC diagnosis from these statistics.')
        result['sources'][identity]=dict(authorization=authorization,provenance=provenance,
            raw_sha256=sha(raw),master=master.relative_to(ROOT).as_posix(),master_sha256=sha(master),
            audio_stream_start=audio.get('start_time'),video_stream_start=video.get('start_time'),
            audio_statistics=stats,video=dict(width=video['width'],height=video['height'],frame_count=len(times),overview=(folder/'overview.jpg').relative_to(ROOT).as_posix()),
            commands=dict(decode=list(map(str,decode)),frames=list(map(str,extract))))
        print(json.dumps(dict(source=identity,master=result['sources'][identity]['master'],audio=stats,video=result['sources'][identity]['video']),ensure_ascii=False),flush=True)
    (OUT/'ingest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
if __name__=='__main__':main()
