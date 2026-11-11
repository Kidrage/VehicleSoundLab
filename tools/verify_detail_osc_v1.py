"""Stream/file parity and actual muted waveOut/UI control verification."""
from runtime_review import ROOT,sha
import json
import subprocess
import sys
import numpy as np
import soundfile as sf
from PIL import Image

OUT=ROOT/'references/analysis/detail_osc_v1'
BUILD=ROOT/'build-detail-osc-v1/Release'


def fingerprint(x):
    h=14695981039346656037
    for b in np.asarray(x,dtype='<f4').tobytes():
        h=((h^b)*1099511628211)&0xffffffffffffffff
    return f'{h:016x}'


def offline(model,reference,acceptance):
    acceptance=json.loads((ROOT/'research/timbre_quality_20261110.json').read_text(encoding='utf-8'))
    model=ROOT/acceptance['model'];reference=ROOT/acceptance['quality_reference']
    assert sha(model)==acceptance['model_sha256'] and sha(reference)==acceptance['quality_reference_sha256']
    ctest=subprocess.run(['ctest','--test-dir',str(ROOT/'build-detail-osc-v1'),'-C','Release','--output-on-failure'],
        check=True,capture_output=True,text=True,timeout=30)
    result=dict(result='pass',reference=acceptance,renders={},ctest=ctest.stdout,native_driving_changed=False)
    for name,pitch in [('unity',1),('lower',.9),('higher',1.1)]:
        target=OUT/f'{name}_float.wav'
        p=subprocess.run([str(BUILD/'detail_osc_probe.exe'),str(model),str(target),str(pitch)],
            check=True,capture_output=True,text=True,timeout=30)
        x,rate=sf.read(target,always_2d=True)
        assert rate==48000 and x.shape[1]==2 and np.isfinite(x).all() and abs(x).max()<.95
        assert abs(len(x)-288000/pitch)<=1.01 and np.array_equal(x[:,0],x[:,1])
        audition=OUT/f'{name}_audition.wav';sf.write(audition,x[:,0],rate,subtype='PCM_24')
        item=dict(relative_varispeed=pitch,frames=len(x),duration=len(x)/rate,float_sha256=sha(target),
            audition_sha256=sha(audition),raw_float_hash=fingerprint(x),log=p.stdout.strip())
        if name=='unity':
            old,sr=sf.read(ROOT/'references/analysis/osc_quality_v2/rank64_c_float.wav',always_2d=True)
            a,ar=sf.read(audition);b,br=sf.read(reference)
            item['max_float_error_to_previous']=float(abs(x-old).max())
            item['max_audition_error_to_reference']=float(abs(a-b).max())
            assert sr==ar==br==rate and item['max_float_error_to_previous']<1e-7
            assert item['max_audition_error_to_reference']<=1/8388608
        result['renders'][name]=item
    return result


def main():
    acceptance=json.loads((ROOT/'research/timbre_quality_20261110.json').read_text(encoding='utf-8'))
    model=ROOT/acceptance['model'];reference=ROOT/acceptance['quality_reference']
    assert sha(model)==acceptance['model_sha256'] and sha(reference)==acceptance['quality_reference_sha256']
    if sys.argv[1:]==['--device-only']:
        result=json.loads((OUT/'verification.json').read_text(encoding='utf-8'))
        for name,item in result['renders'].items():
            assert sha(OUT/f'{name}_float.wav')==item['float_sha256']
            assert sha(OUT/f'{name}_audition.wav')==item['audition_sha256']
        assert (OUT/'attempt1/reason.json').exists()
    else:
        if sys.argv[1:]:raise SystemExit('Use no args for a fresh run or --device-only after preserving the first attempt.')
        OUT.mkdir(exist_ok=False);result=offline(model,reference,acceptance)
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    process=subprocess.run([str(BUILD/'detail_osc_preview.exe'),'--smoke-test',str(model)],cwd=ROOT,
        startupinfo=startup,timeout=30)
    native=json.loads((OUT/'native_preview.json').read_text())
    result['native']=native
    # Save an explicit failure status if the actual device check fails.
    result['result']='pass' if process.returncode==0 and native['result']=='pass' else 'fail'
    (OUT/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    assert process.returncode==0 and native['result']=='pass' and native['device_muted']
    assert native['raw_float_hash']==result['renders']['unity']['raw_float_hash']
    assert native['queue_empty']==native['live_queue_empty']==0 and native['ui_controls']
    assert .95<native['device_seconds']/native['playback_wall_seconds']<1.03
    assert .95<native['live_device_seconds']/native['live_playback_wall_seconds']<1.03
    with Image.open(OUT/'native_preview.bmp') as im:im.save(OUT/'native_preview.png')
    result['binaries']={name:sha(BUILD/name) for name in ['detail_osc_preview.exe','detail_osc_probe.exe','detail_osc_checks.exe']}
    result['source_hashes']={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'experiments/detail_osc_v1').iterdir() if p.is_file()}
    result['result']='pass'
    (OUT/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(result='pass',unity_error=result['renders']['unity']['max_audition_error_to_reference'],
        native=native),indent=2))


if __name__=='__main__':main()
