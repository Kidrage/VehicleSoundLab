"""Convert program-owned native captures for visual review, without listening."""
import argparse
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'host', 'out'):
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
from PIL import Image

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_review.py')
assert load(a.host / 'ui.json')['result'] == 'pass'
rows = []
for name in ('default', 'bench', 'stationary', 'decel', 'F3', 'replay', 'restored'):
    source = a.host / ('ui.json.%s.bmp' % name)
    dest = a.out / (name + '.png')
    with Image.open(source) as im:
        im.convert('RGB').save(dest)
        rows.append(dict(name=name, original_sha256=sha(source), png_sha256=sha(dest), size=list(im.size)))
save(a.out / 'report.json', dict(result='seven_native_images_ready', images=rows, manual_mouse=False, hearing=False))
print('Seven own-window PNGs ready')
