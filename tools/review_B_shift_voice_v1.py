"""Expose unchanged B audio and the excluded peak path, not a replacement fit."""
import argparse
import math
from pathlib import Path
import shutil
import sys
import urllib.request

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace','out'):
    p.add_argument('--'+key,type=Path,required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from PIL import Image
from research_archive_v1 import load,save,sha

root = a.workspace/'references/analysis/B_shift_voice_v1'
a.out.mkdir(parents=True,exist_ok=False)
r = dict(result='running',clips=[],frames=[],sources={})
try:
    audit = load(root/'audit2/report.json')
    assert audit['result']=='passed' and audit['empty_reference_frames']==0
    fit = load(root/'fit1/report.json')
    graph = load(root/'audit2/observed_peak_graph.json')
    reachable = [abs(math.log2(v/fit['anchor']['root_hz']))<=.1 for v in graph['frames'][0]['roots_hz']]
    for before,current in zip(graph['frames'],graph['frames'][1:]):
        prior = [v for v,ok in zip(before['roots_hz'],reachable) if ok]
        reachable = [any(abs(math.log2(v/u))/(current['seconds']-before['seconds'])<=32 for u in prior)
                     for v in current['roots_hz']]
        if not any(reachable):
            frontier = dict(last_reachable_seconds=before['seconds'],last_reachable_roots_hz=prior,
                first_dead_seconds=current['seconds'],next_observed_roots_hz=current['roots_hz'],
                minimum_required_octaves_per_second=min(abs(math.log2(v/u))/(current['seconds']-before['seconds'])
                    for v in current['roots_hz'] for u in prior),declared_maximum=32)
            break
    assert frontier['first_dead_seconds']==audit['reachability']['first_dead_seconds']
    r['failure_frontier']=frontier
    titles={'whole':'完整原声 · 475–485秒','after':'479秒中心原声 · 二挡转弯语境','later':'483秒中心原声 · 降至一挡后的转弯语境'}
    for row in audit['clips']:
        shutil.copy2(root/'audit2'/row['file'],a.out/row['file'])
        assert sha(a.out/row['file'])==row['sha256']
        r['clips'].append(dict(row,title=titles[row['key']]))
    for i,row in enumerate(load(root/'frames1/report.json')['sources']['B']['frames']):
        name=f'picture_{i:02d}.jpg'
        im=Image.open(root/'frames1/B'/row['file']);im.thumbnail((820,462));im.convert('RGB').save(a.out/name,quality=92)
        r['frames'].append(dict(file=name,source_seconds=row['source_seconds'],original_sha256=row['sha256'],sha256=sha(a.out/name)))
    shutil.copy2(root/'audit2/diagnostic.png',a.out/'diagnostic.png')
    save(a.out/'data.json',dict(clips=r['clips'],frames=r['frames'],audio_to_video_seconds=.036291667))
    html=(repo/'tools/B_shift_voice_v1/review.html').read_text(encoding='utf-8').replace('__DATA__',(a.out/'data.json').read_text(encoding='utf-8'))
    (a.out/'index.html').write_text(html,encoding='utf-8',newline='\n')
    for name in ('tools/review_B_shift_voice_v1.py','tools/B_shift_voice_v1/review.html'):
        target=a.out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
        r['sources'][name]=sha(repo/name)
    r['url']='http://127.0.0.1:8789/'+a.out.relative_to(a.workspace).as_posix()+'/index.html'
    for name in ['index.html','data.json','diagnostic.png']+[v['file'] for v in r['clips']]+[v['file'] for v in r['frames']]:
        with urllib.request.urlopen(r['url'].rsplit('/',1)[0]+'/'+name,timeout=10) as response:
            assert response.status==200 and response.read()==(a.out/name).read_bytes()
    r.update(result='three_original_clips_ready',new_voice=False,source_gain=.5,human_hearing=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],failure_frontier=r.get('failure_frontier'),url=r.get('url')))
