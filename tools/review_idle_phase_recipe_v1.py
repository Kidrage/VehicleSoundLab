"""One-player, same-gain idle comparison, exported only after independent checks."""
import argparse,json,shutil,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ['workspace','input','audit','out']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_review.py')
r=dict(result='running',clips=[])
try:
    audit=load(a.audit/'report.json');report=load(a.input/'report.json')
    assert audit['result']=='passed' and audit['input_report_sha256']==sha(a.input/'report.json')
    gain=min(1.,.85/max(max(v['peak'] for v in row['files'].values()) for row in report['renders']))
    for part in ['training','check']:
        x,rate=sf.read(a.input/f'reference_{part}.wav',always_2d=True)
        gain=min(gain,.85/abs(x).max())
    files={};fade=np.sin(np.linspace(0,np.pi/2,1024))**2
    def export(key,path,seconds=None):
        x,rate=sf.read(path,always_2d=True);assert rate==48000
        if seconds is not None:x=x[:seconds*48000]
        y=x*gain;y[:1024]*=fade[:,None];y[-1024:]*=fade[::-1,None]
        out=a.out/(key+'.wav');sf.write(out,y,48000,subtype='PCM_24')
        actual,rate=sf.read(out,always_2d=True);error=float(abs(actual-y).max())
        assert error<=2**-23 and abs(actual).max()<=.85+2**-23
        with urllib.request.urlopen('http://127.0.0.1:8789/'+out.relative_to(a.workspace).as_posix(),timeout=20) as response:
            assert response.read()==out.read_bytes()
        files[key]=out.name;r['clips'].append(dict(key=key,frames=len(y),sha256=sha(out),quantization_error_FS=error))
    for part in ['training','check']:export('reference_'+part,a.input/f'reference_{part}.wav')
    for row in report['renders']:
        seed=row['seed']
        for method in report['methods']:
            detail={'static':'static_detail','post':'post_detail','relation_q':'related_detail','relation_full':'related_detail'}[method]
            for bus,name in [('mix',method),('detail',detail)]:
                export(f'{method}_{seed}_{bus}_short',a.input/row['files'][name]['file'],24)
            if seed==149921:export(f'{method}_{seed}_mix_long',a.input/row['files'][method]['file'])
    template=repo/'tools/idle_phase_recipe_v1/review.html';shutil.copy2(template,a.out/'executed_template.html')
    page=template.read_text(encoding='utf-8').replace('__GAIN__',f'{gain:.6g}').replace('__FILES__',json.dumps(files,separators=(',',':')))
    assert page.count('<audio ')==1 and '__FILES__' not in page and len(files)==30
    (a.out/'index.html').write_text(page,encoding='utf-8')
    url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=20) as response:assert response.read()==(a.out/'index.html').read_bytes()
    r.update(result='same_gain_idle_phase_single_player_review',url=url,common_gain=float(gain),files=files,
      input_report_sha256=sha(a.input/'report.json'),audit_sha256=sha(a.audit/'report.json'),
      listening_accepted=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],url=r.get('url'),clips=len(r['clips']),gain=r.get('common_gain')),flush=True)
