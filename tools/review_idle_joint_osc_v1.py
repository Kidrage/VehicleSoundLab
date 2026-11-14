"""Common-gain diagnostic audition and actual-output measurements, no model tuning."""
import argparse
import json
import shutil
import sys
import urllib.request
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'audit', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out/'executed_review.py')
r = dict(result='running', clips=[], measurements=[], input_report_sha256=sha(a.input/'report.json'),
         audit_sha256=sha(a.audit/'report.json'))
try:
    assert load(a.audit/'report.json')['result'] == 'passed'
    report = load(a.input/'report.json')
    waves, spectra, files = {}, {}, {}
    bands = [[30,120], [120,400], [400,1200], [1200,2200], [2200,4000], [4000,8000], [8000,14000]]
    for row in report['renders']:
        for mode in ['old', 'independent', 'joint']:
            for bus in ['mix', 'detail']:
                x, rate = sf.read(a.input/row['files'][mode+'_'+bus]['file'], always_2d=True)
                assert rate == 48000
                key = f"{mode}_{row['seed']}_{bus}"
                waves[key] = x
                frequency, power = signal.welch(x[:,0], 48000, nperseg=8192)
                spectra[key] = power
                band_power = [float(np.trapezoid(power[(frequency>=lo)&(frequency<hi)],
                                               frequency[(frequency>=lo)&(frequency<hi)])) for lo,hi in bands]
                r['measurements'].append(dict(key=key, rms=float(np.sqrt(np.mean(x*x))),
                                             band_power=band_power))
    origin = a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
    for part in ['train', 'check']:
        with np.load(origin/(part+'.npz')) as f:
            x = f['audio']
        waves['reference_'+part] = x
        _, spectra['reference_'+part] = signal.welch(x[12000:-12000,0],48000,nperseg=8192)
    gain = min(1., .85/max(float(abs(x).max()) for x in waves.values()))
    fade = np.sin(np.linspace(0,np.pi/2,1024))**2
    for key, x in waves.items():
        y = x*gain
        y[:1024] *= fade[:,None]
        y[-1024:] *= fade[::-1,None]
        path = a.out/(key+'.wav')
        sf.write(path,y,48000,subtype='PCM_24')
        actual, rate = sf.read(path,always_2d=True)
        error = float(abs(actual-y).max())
        assert rate == 48000 and error <= 2**-23 and abs(actual).max() <= .85+2**-23
        url = 'http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix()
        with urllib.request.urlopen(url,timeout=20) as response:
            assert response.read() == path.read_bytes()
        files[key] = path.name
        r['clips'].append(dict(key=key,sha256=sha(path),frames=len(y),quantization_error=error))
    template = repo/'tools/idle_joint_osc_v1/review.html'
    shutil.copy2(template,a.out/'executed_template.html')
    page = template.read_text(encoding='utf-8').replace('__GAIN__',f'{gain:.6g}').replace('__FILES__',json.dumps(files))
    assert page.count('<audio ') == 1 and len(files) == 20
    (a.out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    save(a.out/'actual_spectra.json',dict(frequency_hz=frequency.tolist(),spectra={k:v.tolist() for k,v in spectra.items()}))
    url = 'http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=20) as response:
        assert response.read() == (a.out/'index.html').read_bytes()
    r.update(result='diagnostic_single_player_review', common_gain=gain,files=files,url=url,
             bands_hz=bands,actual_PSD_or_RMS_identical=False,listening_accepted=False,runtime_changed=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    raise
finally:
    save(a.out/'report.json',r)
print(dict(result=r['result'],clips=len(r['clips']),gain=r.get('common_gain'),url=r.get('url')),flush=True)
