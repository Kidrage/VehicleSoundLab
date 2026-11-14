"""Same-gain finite audition after extraction/render/observer audits, never a default promotion."""
import argparse,os,shutil,sys,urllib.request,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','render','audit','observation-audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_review.py')
template=repo/'tools/idle_complex75_v1/review.html';shutil.copy2(template,a.out/'executed_template.html')
r=dict(result='running',input_report_sha256=sha(a.render/'report.json'),audit_sha256=sha(a.audit/'report.json'),
    observation_audit_sha256=sha(a.observation_audit/'report.json'),clips=[])
try:
    assert load(a.audit/'report.json')['result']==load(a.observation_audit/'report.json')['result']=='passed'
    render=load(a.render/'report.json');waves={};files={}
    for row in render['renders']:
        for mode,branch in [('0.0',None),('0.5','complex75'),('1.0','independent_old')]:
            for bus in ['mix','main']:
                entry=row['baseline'][bus] if branch is None else row['files'][branch+'_'+bus]
                path=Path(entry['file']) if branch is None else a.render/entry['file'];assert sha(path)==entry['sha256']
                wave,rate=sf.read(path,always_2d=True);assert rate==48000
                waves[f'{mode}_{row["seed"]}_{bus}']=wave
    for part in ['train','check']:
        with np.load(a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'/(part+'.npz')) as f:waves['reference_'+part]=f['audio']
    gain=min(1.,.85/max(float(abs(w).max()) for w in waves.values()));fade=np.sin(np.linspace(0,np.pi/2,1024))**2
    for key,wave in waves.items():
        y=wave*gain;y[:1024]*=fade[:,None];y[-1024:]*=fade[::-1,None]
        path=a.out/(key+'.wav');sf.write(path,y,48000,subtype='PCM_24');actual,rate=sf.read(path,always_2d=True)
        error=float(abs(actual-y).max());assert rate==48000 and error<=2**-23 and abs(actual).max()<=.85+2**-23
        with urllib.request.urlopen('http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix(),timeout=20) as response:assert response.read()==path.read_bytes()
        files[key]=path.name;r['clips'].append(dict(key=key,file=path.name,sha256=sha(path),frames=len(actual),quantization_error=error))
    page=template.read_text(encoding='utf-8').replace('__GAIN__',f'{gain:.6g}').replace('__FILES__',json.dumps(files))
    assert page.count('<audio ')==1 and len(files)==20
    path=a.out/'index.html';path.write_text(page,encoding='utf-8',newline='\n');url='http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=20) as response:assert response.read()==path.read_bytes()
    r.update(result='passed',common_gain=gain,url=url,defaults_stopped=True,single_player=True,listening_accepted=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],url=r.get('url'),clips=len(r['clips']),gain=r.get('common_gain')),flush=True)
