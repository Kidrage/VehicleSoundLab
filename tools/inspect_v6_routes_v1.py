"""Audit pinned public-entry structure, including uninstantiated sample branches."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from v6_route_v1.graph import boxes,inspect,reachable

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--fetch',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


fetch = json.loads((args.fetch/'report.json').read_text(encoding='utf-8'))
assert fetch['result'] == 'pass'
for row in fetch['files']:
    assert sha(args.fetch/'text'/row['path']) == row['sha256'],row['path']
args.out.mkdir(parents=True,exist_ok=False)
graph,documents = inspect(args.fetch/'text')
main = documents['main.maxpat']['patcher']
entries = [b['text'].split(maxsplit=1)[1] for _,b in boxes(main)
           if b.get('text','').startswith('loadunique ')]
assert set(entries) == {'VehicleSoundSynth-EV.maxpat','VehicleSoundSynth-V10.maxpat',
                       'VehicleSoundSynth-V12.maxpat','VehicleSoundSynth-IONIQ6N.maxpat'}
rows = []
for entry in entries+['patchers/vehicle_engine~.maxpat']:
    included = reachable(graph['edges'],entry)
    rows.append(dict(entry=entry,reachable=included,
        sample_read_candidates=[r for r in graph['sample_read_candidates'] if r['path'] in included],
        buffers=[r for r in graph['buffers'] if r['path'] in included],
        gen_operators=[r for r in graph['gen_code_operators'] if r['path'] in included]))
dna = documents['patchers/v10_sound_dna~.maxpat']['patcher']
nodes = {b['id']:b for _,b in boxes(dna)}
assert nodes['obj-4']['text'] == 'v10_powertrain~'
edges = [(tuple(x['patchline']['source']),tuple(x['patchline']['destination'])) for x in dna['lines']]
assert (('obj-4',0),('obj-5',0)) in edges and (('obj-4',1),('obj-6',0)) in edges
public = set(p for r in rows[:-1] for p in r['reachable'])
history = ['patchers/reference_texture~.maxpat','patchers/v10_state_renderer~.maxpat',
           'patchers/v10_fallback_renderer~.maxpat','patchers/v12_texture_renderer~.maxpat']
history_rows = [dict(path=p,public_reachable=p in public,
    read_objects=[r for r in graph['sample_read_candidates'] if r['path']==p]) for p in history]
sources = [Path(__file__),repo/'tools/v6_route_v1/graph.py']
for path in sources:
    target = args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
result = dict(schema='vsl.v6-public-route-audit/1',result='pass',revision=fetch['revision'],
    fetch_report_sha256=sha(args.fetch/'report.json'),public_entries=entries,entries=rows,
    history=history_rows,direct_v10_dna_output=dict(file='patchers/v10_sound_dna~.maxpat',
        source='obj-4 v10_powertrain~',stereo_edges=[['obj-4',0,'obj-5',0],['obj-4',1,'obj-6',0]]),
    graph=graph,source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
    limits=['Static file-instance and literal-reference reachability; not execution in Max',
        'Literal references are conservative, and dependency_cache entries are deliberately excluded',
        'External BEAP/Max objects and arbitrary saved user-state/dynamic runtime commands are not emulated',
        'Buffer presence alone is not evidence of a source loop; IR buffers are processing assets',
        'Public launcher has four entries; legacy generic wrapper remains in the repository',
        'No media fetched, no C/model/UI/drive change, no timbre acceptance'])
(args.out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(public=[dict(entry=r['entry'],files=len(r['reachable']),reads=len(r['sample_read_candidates'])) for r in rows],
    history=history_rows,dynamic=graph['dynamic_construction']),ensure_ascii=False))
