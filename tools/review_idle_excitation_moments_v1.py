"""Export a single-player same-gain idle review, preserving every declared seed."""
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
r=dict(result='running',clips=[],inputs={})
try:
    assert load(a.audit/'report.json')['result']=='passed'
    assert load(a.input/'report.json')['result']=='sparse_excitation_candidates_pending_listening'
    paths={'reference_mix':a.workspace/'baselines/idle_texture_v2/inputs/F2_holdout.wav'}
    for seed in [149921,277139,381611]:
        for mode in ['000','050','100','fast']:
            for bus in ['mix','detail']:
                paths[f'{mode}_{seed}_{bus}']=(a.workspace/f'baselines/idle_conditioned_detail_v1/evidence/trial1/{bus}_050_{seed}.wav'
                    if mode=='fast' else a.input/f'{bus}_{mode}_{seed}.wav')
    audio={}
    for key,path in paths.items():
        audio[key],rate=sf.read(path,always_2d=True);assert rate==48000
        r['inputs'][key]=dict(path=str(path),sha256=sha(path))
    gain=min(1.,.85/max(abs(x).max() for x in audio.values()));files={}
    for key,x in audio.items():
        y=x.copy()*gain;fade=np.sin(np.linspace(0,np.pi/2,1024))**2
        y[:1024]*=fade[:,None];y[-1024:]*=fade[::-1,None]
        path=a.out/(key+'.wav');sf.write(path,y,48000,subtype='PCM_24')
        assert abs(sf.read(path,always_2d=True)[0]-y).max()<=2**-23
        with urllib.request.urlopen('http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix(),timeout=10) as response:
            assert response.read()==path.read_bytes()
        files[key]=path.name;r['clips'].append(dict(key=key,frames=len(y),sha256=sha(path)))
    template=repo/'tools/idle_excitation_moments_v1/review.html'
    page=template.read_text(encoding='utf-8').replace('__GAIN__',format(gain,'.6g')).replace('__FILES__',json.dumps(files,separators=(',',':')))
    (a.out/'index.html').write_text(page,encoding='utf-8');shutil.copy2(template,a.out/'executed_template.html')
    assert page.count('<audio ')==1 and '__FILES__' not in page
    r.update(result='single_player_sparse_idle_review',common_gain=float(gain),files=files,
        url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix(),
        listening_accepted=False,audit_sha256=sha(a.audit/'report.json'))
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r.get('url',r['result']),flush=True)
