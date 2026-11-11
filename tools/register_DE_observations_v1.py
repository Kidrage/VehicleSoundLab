"""Register approved contextual observations; never infer precise RPM from a ridge."""
import json,shutil
from runtime_review import ROOT,sha,rms
from reference_segments import read_segment
import numpy as np
import soundfile as sf

OUT=ROOT/'references/analysis/DE_observations_v1'
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def main():
    if OUT.exists():raise SystemExit('Preserve completed DE observation audit.')
    OUT.mkdir();catalog=ROOT/'references/segments_v1.json'
    shutil.copy2(catalog,OUT/'catalog_before.json')
    data=json.loads(catalog.read_text(encoding='utf-8'));ingest=json.loads((ROOT/'references/analysis/DE_usability_v1/ingest.json').read_text(encoding='utf-8'))
    for source in ['D','E']:
        row=ingest['sources'][source];p=row['provenance']
        data['sources'][source]=dict(url=p['url'],approval='Explicit user approval 2026-11-10: D + E audio/video usability inspection',
            raw=p['raw_file'],raw_sha256=p['sha256'],master=row['master'],master_sha256=row['master_sha256'],
            video=p['raw_file'],video_sha256=p['sha256'],alignment='Same muxed media timeline; no independently measured audiovisual offset. Display latency remains unknown.')
    entries={
        'D_dyno_gears_context':dict(source='D',seconds=[20,32],perspective='Fixed rear-left exterior camera in enclosed dyno cell',
            visual='MAHA dyno/rollers and changing right-hand monitor gauges; publisher caption: dyno run through the gears.',
            audio_interpretation='Unlistened mixed dyno-room recording; inspect transitions before assigning states.',
            allowed_uses=['dyno_context','audio_transition_observation'],not_established=['verified RPM units/readout','ECU RPM or pedal/load telemetry','stock exhaust status','microphone/room transfer','exact gear event times','subjective clarity or absence of music/speech']),
        'E_corsa_first_context':dict(source='E',seconds=[47,55],perspective='Cabin instrument/composite phone footage; Corsa layout',
            visual='Gear1 at47s, gear3 at54s and55s. Tach is a graphical scale; lower-left km field is fuel range.',
            audio_interpretation='Unlistened cabin acceleration context; no continuous RPM fit.',allowed_uses=['gear_display_context','cabin_dynamic_observation'],
            not_established=['continuous unedited run','exact RPM curve','pedal/load','ECU or phone synchronization','external exhaust spectrum']),
        'E_sport_context':dict(source='E',seconds=[58,77],perspective='Cabin instrument/composite phone footage; Sport round tach',
            visual='Gear4 at58s/66s, gear6 at74s/77s. At66s dash189km/h versus phone172km/h.',
            audio_interpretation='Unlistened cabin acceleration/deceleration context; instrument/overlay disagreement recorded.',allowed_uses=['gear_display_context','cabin_dynamic_observation'],
            not_established=['continuous unedited run','exact RPM curve','ECU or phone synchronization','injector state','pedal/load','external exhaust spectrum']),
        'E_corsa_second_context':dict(source='E',seconds=[82,100],perspective='Cabin instrument/composite phone footage; Corsa layout',
            visual='Observed gears1/2/3/4/5/6 at82/84/86/88/90/94s, gear6 at100s. These are discrete observations; intervening continuity has not been established.',
            audio_interpretation='Unlistened mixed cabin recording suitable for subsequent audiovisual shift observation.',allowed_uses=['gear_display_context','cabin_dynamic_observation'],
            not_established=['exact shift/cut timestamps','continuous unedited run','exact RPM curve','pedal/load','ECU or phone synchronization','external exhaust spectrum'])
    }
    for name,row in entries.items():
        if name in data['segments']:raise ValueError('Refuse duplicate registration')
        row['evidence']='references/analysis/DE_details_v1/frames.json'
        data['segments'][name]=row
    data['interval_policy']='Half-open decoded-audio source seconds. D/E include discrete visible instrument context; no verified precise RPM, pedal/load or injector telemetry. Uses are restricted per segment.'
    write(catalog,data)
    result=dict(catalog_sha256=sha(catalog),segments={},subjective_listening_performed=False,
        D_gauge='27.994s upper-right readout appears7093; unit/label not conclusively resolved. Keep as tentative display transcription, not RPM.',
        E_dash='Graphical tach with x1000 scale can support approximate display readings after calibration. Fuel range is not RPM; phone is not verified synchronized telemetry.',
        limitations='No automated fit, denoise, EQ or source separation. New clips use fixed -6.0206dB and 5ms endpoints, stereo preserved. Mixed cabin/dyno transfer is not exterior A transfer.')
    for name,row in entries.items():
        x,rate,p=read_segment(name,row['allowed_uses'][0]);fade=round(.005*rate)
        y=x*.5;ramp=.5-.5*np.cos(np.linspace(0,np.pi,fade));y[:fade]*=ramp[:,None];y[-fade:]*=ramp[::-1,None]
        path=OUT/(name+'.wav');sf.write(path,y,rate,subtype='PCM_24')
        result['segments'][name]=dict(provenance=p,audition=path.relative_to(ROOT).as_posix(),sha256=sha(path),gain_db=-6.020599913279624,endpoint_fade_ms=5,
            raw_rms_dbfs=rms(x),raw_peak=float(abs(x).max()),audition_peak=float(abs(y).max()),frames=len(x))
    write(OUT/'observations.json',result)
    shutil.copy2(catalog,OUT/'catalog_after.json')
    print('D/E registered through hash-checked stereo reader; contextual uses only. Four fixed-headroom clips.')
if __name__=='__main__':main()
