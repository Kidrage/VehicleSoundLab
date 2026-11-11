"""Complete the first snapshot's build metadata; do not alter its DSP or audio."""
from pathlib import Path
import shutil
import hashlib
import json
root=Path(__file__).resolve().parents[1];folder=root/'baselines/v0.1.0'
if not (folder/'tests').exists():shutil.copytree(root/'tests',folder/'tests')
manifest=folder/'manifest.json';data=json.loads(manifest.read_text())
present={v['path'] for v in data['files']}
for path in list((folder/'tests').rglob('*'))+[folder/'CMakeLists.txt']:
    name=str(path.relative_to(folder))
    if path.is_file() and name not in present:
        data['files'].append(dict(path=name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
manifest.write_text(json.dumps(data,indent=2),encoding='utf-8')
