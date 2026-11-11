"""Run this app's own muted device and message-loop checks, no OS input injection."""
import json,subprocess,shutil
from runtime_review import ROOT,sha
from review_audit import device
from PIL import Image
OUT=ROOT/'renders/app0.20.0'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def main():
    if (OUT/'ui_smoke.json').exists():raise SystemExit('Preserve existing native attempt before another run.')
    OUT.mkdir(exist_ok=True,parents=True)
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    exe=ROOT/'build-v020/Release/VehicleSoundLab.exe'
    for switch in ['--smoke-test','--ui-input-check']:
        subprocess.run([str(exe),switch],cwd=ROOT,startupinfo=startup,check=True,timeout=60)
    native=read('ui_smoke.json');device(native,'0.20.0')
    assert all(v for v in native.values() if isinstance(v,bool)),[k for k,v in native.items() if v is False]
    take=read('ui_take_smoke.json');assert all(v==1 for k,v in take.items() if k!='result')
    t=take['result']
    for key in ['saved','loaded','offline_hash_match','final_drive_state_match','device_replay_hash_and_state_match','manual_replay_stop','controls_locked','muted']:assert t[key]==1,key
    assert t['dsp']=='0.20.0' and t['replay_queue_empty']==0 and .95<t['replay_device_seconds']/t['replay_wall_seconds']<1.02
    keys=read('ui_input.json');assert keys['app']==keys['dsp']=='0.20.0'
    assert all(keys[k]==1 for k in ['SCI_FI_type_search','selection_does_not_brake','mode_selection_does_not_shift','brake_shortcut','brake_release_after_focus_change','throttle_shortcut','throttle_release_after_focus_change','focus_loss_releases_pedals'])
    assert all(read('ui_take_controls.json').values())
    log=ROOT/'build-v020/Testing/Temporary/LastTest.log';assert log.read_bytes().count(b'Test Passed.')==23
    shutil.copy2(log,OUT/'ctest.log')
    for path in OUT.glob('*.bmp'):
        with Image.open(path) as im:im.save(path.with_suffix('.png'))
    result=dict(result='pass',app='0.20.0',dsp='0.20.0',ctest_count=23,native=native,take=take,input=keys,
        executable_sha256=sha(exe),limits='Muted output validates device scheduling and exact pre-device replay, not physical loopback or subjective realism.')
    (OUT/'native_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',render_ms_mean=native['render_ms_mean'],render_ms_max=native['render_ms_max'],device_wall_ratio=native['device_seconds']/native['wall_seconds'],pulse_controls=native['pulse_controls'],pulse_active=native['pulse_active_on_device'],take_hash_match=t['device_replay_hash_and_state_match']),indent=2))
if __name__=='__main__':main()
