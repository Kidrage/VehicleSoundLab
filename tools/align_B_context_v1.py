"""Measure user MP3 alignment to approved same-source video audio in five windows."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--fetch',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from cabin_low_v1.alignment import locate,controls
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.b-audio-alignment/1',result='running',sources={},windows=[])
try:
    plan_path=repo/'research/B_alignment_v1_plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    for file in [Path(__file__),plan_path,repo/'tools/cabin_low_v1/alignment.py',
                 repo/'tools/drive_evidence_v1/sources.py']:
        name=file.relative_to(repo);target=a.out/'exact_sources'/name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
        r['sources'][name.as_posix()]=sha(file)
    fetched=json.loads((a.fetch/'report.json').read_text(encoding='utf-8'))
    assert fetched['result']=='downloaded_audio_not_aligned'
    assert fetched['url']=='https://www.youtube.com/watch?v=qmp1SVhmXgU'
    encoded=Path(fetched['file']);assert sha(encoded)==fetched['sha256']
    catalog_path=a.workspace/'references/segments_v1.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    b=catalog['sources']['B'];master=a.workspace/b['master']
    assert sha(master)==b['master_sha256']
    probe=subprocess.check_output(['ffprobe','-v','error','-show_entries',
        'stream=index,codec_type,time_base,start_pts,start_time,sample_rate,channels,duration',
        '-of','json',str(encoded)])
    (a.out/'probe.json').write_bytes(probe)
    stream=next(s for s in json.loads(probe)['streams'] if s['codec_type']=='audio')
    start_pts_seconds=float(stream['start_time'])
    decoded=a.out/'B_video_audio_decoded_float.wav'
    command=['ffmpeg','-nostdin','-n','-v','error','-i',str(encoded),
        '-map','0:a:0','-ar','48000','-ac','2','-c:a','pcm_f32le',str(decoded)]
    done=subprocess.run(command,capture_output=True,timeout=60)
    (a.out/'decode.log').write_bytes(done.stdout+done.stderr);assert done.returncode==0
    r['input']=dict(master_sha256=sha(master),encoded_audio_sha256=sha(encoded),
        fetch_report_sha256=sha(a.fetch/'report.json'),catalog_sha256=sha(catalog_path),
        decoded_sha256=sha(decoded),audio_stream_start_seconds=start_pts_seconds,
        command=command)
    r['controls']=controls()
    rate=48000;duration=plan['template_seconds'];half=plan['search_half_width_seconds'];padding=.25
    sos=signal.butter(4,plan['filter_hz'],btype='bandpass',fs=rate,output='sos')
    with sf.SoundFile(master) as old,sf.SoundFile(decoded) as new:
        assert old.samplerate==new.samplerate==rate and old.channels==new.channels==2
        r['durations_seconds']=[len(old)/rate,len(new)/rate]
        for t in plan['template_starts_seconds']:
            old.seek(round((t-padding)*rate));new.seek(round((t-half-padding)*rate))
            x=old.read(round((duration+2*padding)*rate),dtype='float64',always_2d=True)
            y=new.read(round((duration+2*half+2*padding)*rate),dtype='float64',always_2d=True)
            assert len(x)==round((duration+2*padding)*rate)
            assert len(y)==round((duration+2*half+2*padding)*rate)
            x=signal.sosfiltfilt(sos,x,axis=0)[round(padding*rate):-round(padding*rate)]
            y=signal.sosfiltfilt(sos,y,axis=0)[round(padding*rate):-round(padding*rate)]
            channels=[]
            for c in range(2):
                found=locate(x[:,c],y[:,c],rate)
                found['video_audio_minus_user_audio_seconds']=found['start_sample']/rate-half+start_pts_seconds
                found['unique_match']=bool(found['ncc']>=plan['minimum_ncc'] and
                    found['peak_margin']>=plan['minimum_peak_margin_outside_5ms'])
                channels.append(found)
            delta=abs(channels[0]['video_audio_minus_user_audio_seconds']-channels[1]['video_audio_minus_user_audio_seconds'])
            row=dict(user_audio_seconds=[t,t+duration],channels_LR=channels,
                channel_offset_difference_ms=1000*delta,
                passed=all(v['unique_match'] for v in channels) and delta<=plan['maximum_channel_offset_difference_ms']/1000)
            r['windows'].append(row);print(json.dumps(row),flush=True)
    offsets=[v['video_audio_minus_user_audio_seconds'] for w in r['windows'] for v in w['channels_LR']]
    spread=1000*(max(offsets)-min(offsets))
    passed=all(w['passed'] for w in r['windows']) and spread<=plan['maximum_cross_window_offset_range_ms']
    r.update(result='audio_timeline_alignment_pass' if passed else 'audio_timeline_alignment_not_qualified',
        offset_range_ms=spread,median_video_audio_minus_user_audio_seconds=float(np.median(offsets)),
        plan=plan,limits=['Audio-to-audio alignment only; not independent engine-event/instrument/video latency calibration',
            'No audio, video, RPM mapping, DNA or controller modified',
            'Five local matches do not prove every intervening sample is unedited'])
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
