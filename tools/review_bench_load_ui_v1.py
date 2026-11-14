"""Convert only program-owned native captures and retain their identities."""
import argparse
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','host','out'):
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from PIL import Image
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_review.py')
assert load(a.host/'ui.json')['result']=='pass'
rows=[]
for name in ('default','bench','stationary','decel','replay','restored'):
    source=a.host/f'ui.json.{name}.bmp'
    with Image.open(source) as im:
        im.convert('RGB').save(a.out/(name+'.png'))
        rows.append(dict(name=name,original_sha256=sha(source),png_sha256=sha(a.out/(name+'.png')),size=list(im.size)))
save(a.out/'report.json',dict(result='six_native_images_ready',images=rows,manual_mouse=False,hearing=False))
print('Six own-window PNGs ready')
