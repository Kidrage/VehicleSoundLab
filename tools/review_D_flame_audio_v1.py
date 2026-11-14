"""Build the four fixed original-audio excerpts with sampled picture context."""
import argparse,shutil,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from PIL import Image
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);root=a.workspace/'references/analysis/D_flame_audio_v1'
r=dict(result='running',clips=[],frames=[])
try:
    labels={'whole':'完整语境 · 36–44秒','before':'前段原声 · 36–38秒','primary':'火焰附近原声 · 38–42秒','after':'后段原声 · 42–44秒'}
    for row in load(root/'audio1/report.json')['clips']:
        shutil.copy2(root/'audio1'/row['file'],a.out/row['file']);assert sha(a.out/row['file'])==row['sha256']
        r['clips'].append(dict(row,title=labels[row['key']]))
    for i,row in enumerate(load(root/'frames1/report.json')['sources']['D']['frames']):
        name=f'picture_{i:02d}.jpg';im=Image.open(root/'frames1/D'/row['file']);im.thumbnail((820,462));im.convert('RGB').save(a.out/name,quality=92)
        r['frames'].append(dict(file=name,source_seconds=row['source_seconds'],original_sha256=row['sha256'],thumbnail_sha256=sha(a.out/name)))
    shutil.copy2(root/'audio1/diagnostic.png',a.out/'diagnostic.png')
    save(a.out/'data.json',dict(clips=r['clips'],frames=r['frames']))
    html=(repo/'tools/flame_audio_v1/review.html').read_text(encoding='utf-8').replace('__DATA__',(a.out/'data.json').read_text(encoding='utf-8'))
    (a.out/'index.html').write_text(html,encoding='utf-8',newline='\n')
    r['url']='http://127.0.0.1:8789/'+a.out.relative_to(a.workspace).as_posix()+'/index.html'
    for name in ['index.html','data.json','diagnostic.png']+[v['file'] for v in r['clips']]+[v['file'] for v in r['frames']]:
        url=r['url'].rsplit('/',1)[0]+'/'+name
        with urllib.request.urlopen(url,timeout=10) as response:assert response.status==200 and response.read()==(a.out/name).read_bytes()
    for n in ['tools/review_D_flame_audio_v1.py','tools/flame_audio_v1/review.html']:
        dest=a.out/'exact_sources'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/n,dest)
    r.update(result='four_original_clips_ready',single_player=True,source_gain=.5,new_fitted_voice=False,human_listening=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],url=r.get('url')))
