"""Frozen-source parity and actual muted device/UI lifecycle checks."""
from runtime_review import ROOT,sha
import json
import subprocess
import sys
import numpy as np
import soundfile as sf
from PIL import Image

OUT=ROOT/'references/analysis/sustain_monitor_v1'
BUILD=ROOT/'build-sustain-monitor-v1/Release'
PROFILE=ROOT/'references/analysis/sustain_osc_v1/voice.model'


def fingerprint(x):
    h=14695981039346656037
    for b in np.asarray(x,dtype='<f4').tobytes():h=((h^b)*1099511628211)&0xffffffffffffffff
    return f'{h:016x}'


def main():
    resume=sys.argv[1:]==['--resume-evidence']
    if sys.argv[1:] and not resume:raise SystemExit('Use no args or --resume-evidence after preserving an assertion failure.')
    if resume:
        assert (OUT/'attempt1/reason.json').exists()
    else:OUT.mkdir(exist_ok=False)
    assert sha(PROFILE)=='6f8992e6674f603334f82bdbc526fd8ac5bbe750606154c5e83c166c077bb1b7'
    check=subprocess.run(['ctest','--test-dir',str(ROOT/'build-sustain-monitor-v1'),'-C','Release','--output-on-failure'],
        capture_output=True,text=True,timeout=30,check=True)
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    if resume:
        returncode=json.loads((OUT/'verification.json').read_text())['device_returncode']
    else:
        returncode=subprocess.run([str(BUILD/'sustain_osc_monitor.exe'),'--smoke-test',str(PROFILE)],cwd=ROOT,startupinfo=startup,timeout=50).returncode
    native=json.loads((OUT/'native_preview.json').read_text())
    result=dict(result='pending',ctest=check.stdout,native=native,device_returncode=returncode,
        profile_sha256=sha(PROFILE),frozen_source_used=True)
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    assert returncode==0 and native['result']=='pass'
    assert native['device_muted'] and native['controls_isolated'] and native['stop_and_restart'] and native['close_while_playing']
    for key in ['baseline','live','stopped','closed']:
        item=native[key]
        assert item['opened'] and not item['error'] and item['queue_empty']==0
        if key in ['baseline','live']:
            assert .95<item['device_seconds']/item['playback_wall_seconds']<1.03
        else:
            #Subsecond stop/close includes fixed device teardown latency.
            #Use an absolute drain-overhead bound rather than a speed estimate.
            assert 0<=item['playback_wall_seconds']-item['device_seconds']<.060
        assert item['render_ms_mean']<512/48
    original,sr=sf.read(ROOT/'references/analysis/sustain_osc_v1/renders/generated_float.wav',always_2d=True)
    baseline,rate=sf.read(OUT/'baseline_device.wav',always_2d=True)
    assert sr==rate==48000 and original.shape==baseline.shape==(384000,2)
    assert native['baseline']['raw_float_hash']==fingerprint(original)
    expected=original*.5;expected[:240]*=np.arange(240)[:,None]/239
    error=float(abs(baseline-expected).max());assert error<6e-8
    audition,rate=sf.read(ROOT/'references/analysis/sustain_osc_v1/renders/generated_audition.wav',always_2d=True)
    #5ms start envelope matches; continuous monitor has no8s end fade.
    assert rate==48000 and abs(baseline[:-240]-audition[:-240]).max()<=1/8388608+6e-8
    live,rate=sf.read(OUT/'live_device.wav',always_2d=True)
    stopped,rate=sf.read(OUT/'stopped_device.wav',always_2d=True)
    assert live.shape==(384000,2) and np.isfinite(live).all() and not np.array_equal(live,baseline)
    assert (stopped[-16:]==0).all() and np.isfinite(stopped).all()
    with Image.open(OUT/'native_preview.bmp') as im:im.save(OUT/'native_preview.png')
    result.update(result='pass',unmodified_source_float_hash=fingerprint(original),max_device_pre_envelope_error=error,
        render_note='Capture is pre-mute/pre-device: not a soundcard loopback. Common0.5 headroom; no compressor/EQ or extra spatial processing.',
        timing_note='8s runs check playback rate. Subsecond stop/close checks bounded<=60ms drain/teardown overhead, not playback speed.',
        exact_source_recipe_preserved=True,native_driving_DSP020_changed=False,goal_complete=False,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'experiments/sustain_monitor_v1').iterdir() if p.is_file()},
        binaries={name:sha(BUILD/name) for name in ['sustain_osc_monitor.exe','sustain_monitor_checks.exe']},
        evidence={str(p.relative_to(ROOT)):sha(p) for p in OUT.glob('*') if p.is_file() and p.name!='verification.json'})
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',source_hash=result['unmodified_source_float_hash'],device_envelope_error=error,native=native),indent=2))


if __name__=='__main__':main()
