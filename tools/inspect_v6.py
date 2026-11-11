"""Snapshot additional V6 control/patch text, never media; keep the original snapshot."""
from pathlib import Path
import sys,json,urllib.request,hashlib
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]
tree=json.loads((ROOT/'research/v6_tree.json').read_text(encoding='utf-8-sig'))
rev=tree['sha']
names=[x['path'] for x in tree['tree'] if x['type']=='blob' and
       (x['path'].startswith('code/') and x['path'].endswith('.js') or
        x['path'] in ['main.maxpat','VehicleSoundSynth-V6.maxproj','ASSET_LICENSES.md',
        '.codex/MAINLINE.md','patchers/engine_controller_v10.maxpat',
        'patchers/drive_simulator.maxpat','patchers/v10_powertrain~.maxpat',
        'patchers/v10_pad_driver~.maxpat','patchers/v10_soundscape_host~.maxpat',
        'patchers/v10_engine_start_host~.maxpat','patchers/v10_backfire_host~.maxpat',
        'presets/v10_soundscape_v4_factory.json','presets/ev_soundscape_v4_factory.json',
        'gen/v12_powertrain.gendsp','gen/ev_powertrain.gendsp','assets/ferrari_v10_lifecycle_targets.json',
        'VehicleSoundSynth-V10.maxpat','VehicleSoundSynth-V12.maxpat','VehicleSoundSynth-EV.maxpat',
        'VehicleSoundSynth-IONIQ6N.maxpat','patchers/v10_pad_host~.maxpat',
        'patchers/v10_cinematic_soundscape_host~.maxpat','patchers/v10_soundscape_v4_beap~.maxpat'])]
def fetch(name):
    data=urllib.request.urlopen(f'https://raw.githubusercontent.com/Kidrage/VehicleSoundSynth/{rev}/{name}',timeout=30).read()
    out=ROOT/'research/upstream_v6'/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
    return dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
with ThreadPoolExecutor(max_workers=6) as pool: results=list(pool.map(fetch,names))
(ROOT/'research/v6_control_snapshot.json').write_text(json.dumps(dict(revision=rev,files=results),indent=2),encoding='utf-8')
def summarize(patch):
    p=json.loads(patch.read_text(encoding='utf-8'))['patcher']
    return dict(path=str(patch.relative_to(ROOT)),objects=[b['box'].get('text',b['box'].get('maxclass','')) for b in p.get('boxes',[])],connections=len(p.get('lines',[])))
patches=[summarize(p) for p in (ROOT/'research/upstream_v6').rglob('*.maxpat')]
(ROOT/'research/v6_patch_summary.json').write_text(json.dumps(patches,indent=2,ensure_ascii=False),encoding='utf-8')
print('Pinned',rev,'text files',len(results),'patches',len(patches))
