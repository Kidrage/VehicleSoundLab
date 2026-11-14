"""One-player common-gain review of the projected-residual comparison."""
import argparse,json,shutil,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_review.py')
r=dict(result='running',clips=[],input_report_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'))
try:
    assert load(a.audit/'report.json')['result']=='passed'
    report=load(a.input/'report.json');files={};waves={}
    assert report['result']=='finite_separated_low_residual_pending_audit'
    for row in report['renders']:
        for amount in ['0.0','0.5','1.0']:
            for bus in ['mix','main']:
                path=a.input/row['files'][bus+'_'+amount]['file']
                waves[f"{amount}_{row['seed']}_{bus}"]=sf.read(path,always_2d=True)[0]
    origin=a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
    for part in ['train','check']:
        with np.load(origin/(part+'.npz')) as f:waves['reference_'+part]=f['audio']
    gain=min(1.,.85/max(float(abs(x).max()) for x in waves.values()))
    fade=np.sin(np.linspace(0,np.pi/2,1024))**2
    for key,x in waves.items():
        y=x*gain;y[:1024]*=fade[:,None];y[-1024:]*=fade[::-1,None]
        path=a.out/(key+'.wav');sf.write(path,y,48000,subtype='PCM_24')
        actual,rate=sf.read(path,always_2d=True);error=float(abs(actual-y).max())
        assert rate==48000 and error<=2**-23 and abs(actual).max()<=.85+2**-23
        with urllib.request.urlopen('http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix(),timeout=20) as response:assert response.read()==path.read_bytes()
        files[key]=path.name;r['clips'].append(dict(key=key,sha256=sha(path),frames=len(y),quantization_error=error))
    template=repo/'tools/idle_phase_amplitude_v1/residual_review.html';shutil.copy2(template,a.out/'executed_template.html')
    page=template.read_text(encoding='utf-8').replace('__GAIN__',f'{gain:.6g}').replace('__FILES__',json.dumps(files))
    assert page.count('<audio ')==1 and len(files)==20
    (a.out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=20) as response:assert response.read()==(a.out/'index.html').read_bytes()
    r.update(result='same_gain_idle_separated_residual_review',common_gain=gain,files=files,url=url,listening_accepted=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],clips=len(r['clips']),gain=r.get('common_gain'),url=r.get('url')),flush=True)
