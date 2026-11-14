"""Reusable finite main/mix comparison export; synthesis and page styling stay separate."""
import json,shutil,urllib.request
from pathlib import Path
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha


def build(workspace,source,audit,out,template,expected_result,executed_wrapper):
    workspace=Path(workspace);source=Path(source);audit=Path(audit);out=Path(out);template=Path(template)
    out.mkdir(parents=True,exist_ok=False);shutil.copy2(executed_wrapper,out/'executed_review.py')
    shutil.copy2(__file__,out/'executed_exporter.py');shutil.copy2(template,out/'executed_template.html')
    r=dict(result='running',clips=[],input_report_sha256=sha(source/'report.json'),audit_sha256=sha(audit/'report.json'))
    try:
        assert load(audit/'report.json')['result']=='passed'
        report=load(source/'report.json');assert report['result']==expected_result;waves={};files={}
        for row in report['renders']:
            for condition in ['0.0','0.5','1.0']:
                for bus in ['mix','main']:
                    entry=row['files'][bus+'_'+condition];path=source/entry['file'];assert sha(path)==entry['sha256']
                    waves[f"{condition}_{row['seed']}_{bus}"]=sf.read(path,always_2d=True)[0]
        origin=workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
        for part in ['train','check']:
            with np.load(origin/(part+'.npz')) as f:waves['reference_'+part]=f['audio']
        gain=min(1.,.85/max(float(abs(x).max()) for x in waves.values()))
        fade=np.sin(np.linspace(0,np.pi/2,1024))**2
        for key,x in waves.items():
            y=x*gain;y[:1024]*=fade[:,None];y[-1024:]*=fade[::-1,None]
            path=out/(key+'.wav');sf.write(path,y,48000,subtype='PCM_24')
            actual,rate=sf.read(path,always_2d=True);error=float(abs(actual-y).max())
            assert rate==48000 and error<=2**-23 and abs(actual).max()<=.85+2**-23
            with urllib.request.urlopen('http://127.0.0.1:8789/'+path.relative_to(workspace).as_posix(),timeout=20) as response:assert response.read()==path.read_bytes()
            files[key]=path.name;r['clips'].append(dict(key=key,file=path.name,sha256=sha(path),frames=len(y),quantization_error=error))
        page=template.read_text(encoding='utf-8').replace('__GAIN__',f'{gain:.6g}').replace('__FILES__',json.dumps(files))
        assert page.count('<audio ')==1 and len(files)==20
        (out/'index.html').write_text(page,encoding='utf-8',newline='\n')
        url='http://127.0.0.1:8789/'+(out/'index.html').relative_to(workspace).as_posix()
        with urllib.request.urlopen(url,timeout=20) as response:assert response.read()==(out/'index.html').read_bytes()
        r.update(result='same_gain_finite_main_mix_review',common_gain=gain,files=files,url=url,listening_accepted=False,runtime_changed=False)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(out/'report.json',r)
    return r
