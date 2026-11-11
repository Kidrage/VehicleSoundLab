"""Actual muted device/UI checks for the independent low layer."""
from runtime_review import ROOT,sha
import json
import subprocess
import numpy as np
import soundfile as sf
from PIL import Image

OUT=ROOT/'references/analysis/sustain_monitor_v4'
BUILD=ROOT/'build-sustain-monitor-v4/Release'
DNA=ROOT/'voices/dna_bank_v1/V10 Exterior.model'
LOW=ROOT/'voices/low_rumble_v2/A Exterior.model'


def main():
    OUT.mkdir(exist_ok=False)
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    code=subprocess.run([str(BUILD/'sustain_osc_monitor.exe'),'--smoke-test',str(DNA),str(LOW)],cwd=ROOT,startupinfo=startup,timeout=50).returncode
    native=json.loads((OUT/'native_preview.json').read_text());bank=json.loads((OUT/'bank_checks.json').read_text())
    pending=dict(result='pending',device_returncode=code,native=native,bank_checks=bank)
    (OUT/'verification.json').write_text(json.dumps(pending,indent=2),encoding='utf-8')
    assert code==0 and native['result']=='pass' and bank['result'] and bank['voice_count']==4 and bank['DNA_unchanged']
    assert native['controls_isolated'] and native['stop_and_restart'] and native['close_while_playing']
    for key in ['baseline','live','stopped','closed']:
        s=native[key];assert s['opened'] and not s['error'] and s['queue_empty']==0
        if key in ['baseline','live']:assert .95<s['device_seconds']/s['playback_wall_seconds']<1.03
        else:assert 0<=s['playback_wall_seconds']-s['device_seconds']<.060
        assert s['render_ms_mean']<512/48
    assert native['baseline']['raw_float_hash']=='89079981f900fd12'
    baseline,rate=sf.read(OUT/'baseline_device.wav',always_2d=True)
    assert rate==48000 and baseline.shape==(384000,2) and abs(baseline).max()<.95
    # Build the expected default independently using the same public offline
    # probe. Its path differs from the native device/capture path.
    output=OUT/'expected_default_float.wav'
    subprocess.run([str(BUILD/'low_rumble_probe.exe'),str(DNA),str(LOW),str(output),'8','1','.6','0','0'],check=True,timeout=20)
    expected,rate=sf.read(output,always_2d=True);assert np.array_equal(baseline,expected)
    stopped,rate=sf.read(OUT/'stopped_device.wav',always_2d=True);assert (stopped[-16:]==0).all()
    with Image.open(OUT/'native_preview.bmp') as im:im.save(OUT/'native_preview.png')
    pending.update(result='pass',native_matches_offline_default_exactly=True,DNA_unchanged=True,
        device_capture='Pre-mute/pre-device;not soundcard loopback.',
        visual_limit='Own hidden-window capture; no visible desktop inspection or subjective acceptance claimed.',
        low_layer_subjective_acceptance=False,goal_complete=False,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for folder in ['modules/low_rumble','modules/sound_dna','experiments/sustain_monitor_v4'] for p in (ROOT/folder).iterdir() if p.is_file()},
        binaries={p.name:sha(p) for p in BUILD.glob('*.exe')},
        evidence={str(p.relative_to(ROOT)):sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='verification.json'})
    (OUT/'verification.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',baseline=native['baseline'],live=native['live'],bank=bank),indent=2))


if __name__=='__main__':main()
