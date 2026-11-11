"""Shared read-only artifact checks for versioned local listening reviews."""
import json
from runtime_review import ROOT,sha,rms
import numpy as np
import soundfile as sf


def read_json(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def pair(out,takes,tags,raw=None):
    gains=[];checked={}
    for tag in tags:
        item=takes[tag];path=out/item['file'];x,rate=sf.read(path,always_2d=True)
        assert sha(path)==item['sha256'] and rate==48000 and sf.info(path).subtype=='PCM_24'
        assert x.shape[1]==2 and np.isfinite(x).all() and abs(x).max()<=.850001
        assert abs(rms(x)-item['raw_rms_dbfs']-item['gain_db'])<.001
        if raw is not None:
            y,sr=sf.read(raw[tag],always_2d=True)
            assert sr==rate and x.shape==y.shape and np.max(abs(x-y*10**(item['gain_db']/20)))<1.3e-7
        gains.append(item['gain_db']);checked[path.name]=dict(sha256=sha(path),gain_db=item['gain_db'])
    assert len(set(gains))==1
    return checked


def frozen_baselines(counts):
    checked={}
    for version,count in counts.items():
        folder=ROOT/'baselines'/version;manifest=read_json(folder/'manifest.json')
        assert len(manifest['files'])==count
        for item in manifest['files']:assert sha(folder/item['path'])==item['sha256'],(version,item['path'])
        checked[version]=count
    return checked


def device(report,version):
    assert report['dsp']==version
    for key in ['device_stream_muted','waveOut_opened_and_queued_audio','running_latch','manual_shift','shutdown_to_off','export_succeeded',
        'fuel_controls','fuel_preset_roundtrip','control_isolation','mechanical_control','mechanical_preset_roundtrip',
        'legacy_preset_retains_mechanical_voice','combustion_control','combustion_preset_roundtrip','legacy_preset_retains_pressure_voice']:
        assert report[key],key
    assert report['queue_empty_observations']==0 and .95<report['device_seconds']/report['wall_seconds']<1.02
    assert report['render_ms_mean']<report['block_frames']/48
