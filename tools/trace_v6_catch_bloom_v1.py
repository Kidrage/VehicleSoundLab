"""Trace literal V6 Catch Bloom control/audio separately from Crank Body."""
import argparse,collections,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_trace.py')
root=a.workspace/'references/analysis/upstream_route_v1/fetch2'
source=root/'text/patchers/v10_engine_start_v3_beap~.maxpat'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
fetch=json.loads((root/'report.json').read_text(encoding='utf-8'))
assert fetch['result']=='pass'
row=next(v for v in fetch['files'] if v['path']=='patchers/v10_engine_start_v3_beap~.maxpat')
assert sha(source)==row['sha256'];shutil.copy2(source,a.out/source.name)
patch=json.loads(source.read_text(encoding='utf-8-sig'))['patcher']
nodes={v['box']['id']:v['box'] for v in patch['boxes']}
edges=[v['patchline'] for v in patch['lines']]
def path(first,last):
    queue=collections.deque([(first,[])]);seen={first}
    while queue:
        node,used=queue.popleft()
        if node==last:return used
        for edge in edges:
            dest=edge['destination'][0]
            if edge['source'][0]==node and dest not in seen:
                seen.add(dest);queue.append((dest,used+[edge]))
    raise AssertionError((first,last))
expected={'obj-30':'Catch Bloom','obj-32':'clip 0. 1.','obj-33':'sig~ 0.',
    'obj-34':'rampsmooth~ 128 256','obj-35':'0.88','obj-79':'cycle~',
    'obj-76':'reson~ 3.4 92 4.2','obj-75':'lores~ 520 0.72'}
for key,value in expected.items():assert nodes[key].get('text')==value
paths=dict(catch_control=path('obj-31','obj-81'),catch_audio=path('obj-79','obj-105'),
    crank_resonance=path('obj-76','obj-105'))
assert any(v['source']==['obj-34',0] and v['destination']==['obj-81',1] for v in paths['catch_control'])
assert all(v['source'][0]!='obj-76' for v in paths['catch_audio'])
report=dict(result='literal_paths_checked',revision=fetch['revision'],patch_sha256=sha(source),paths=paths,
    nodes={k:{f:v for f,v in nodes[k].items() if f in ('id','text','maxclass')} for k in sorted({x[i][0] for y in paths.values() for x in y for i in ('source','destination')})},
    meaning='Catch Bloom is cycle~ gain branch;92Hz resonator is Crank/Activation Body, not Catch Bloom',
    borrowed='Independent state-layer control, not its tone/frequency/gain values',Max_executed=False)
(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:report[k] for k in ('result','revision','meaning')}))
