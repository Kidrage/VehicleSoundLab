"""Collect final device/UI evidence without rerendering sound."""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/python_deps'))
from PIL import Image
out=ROOT/'renders/v0.3.0'
app=ROOT/'build/Release/VehicleSoundLab.exe'
smoke=ROOT/'renders/ui_smoke.json'
assert smoke.stat().st_mtime>=app.stat().st_mtime,'Run the actual final UI binary first'
assert json.loads(smoke.read_text())['dsp']=='0.3.0'
for name in ['ui_detail','ui_listening','ui_ready']:
    with Image.open(ROOT/'renders'/f'{name}.bmp') as im:
        if name=='ui_detail':assert im.width>=650 and im.height>=380,'Detail panel clips the activity indicators'
        im.save(out/f'{name}.png')
for source,target in [('ui_smoke.json','ui_smoke.json'),('dna_pipeline_check.json','dna_pipeline_check.json'),('v03_ctest.xml','ctest.xml')]:
    shutil.copyfile(ROOT/'renders'/source,out/target)
# Render-owned files only. UI snapshots/device evidence have their own audit.
verification=json.loads((out/'verification.json').read_text())
verification['files']={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(out.rglob('*')) if not p.name.startswith('ui_') and
    (p.suffix in ['.wav','.csv','.png'] or p.name.endswith('_scene.json'))}
(out/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
print('Collected final UI, device, CTest and DNA evidence')
