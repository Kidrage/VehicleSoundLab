"""Bind verification to exact source files, assets and binary bytes."""
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture(repo,output,binary=None):
    repo=Path(repo);output=Path(output);selected=set()
    for folder in ('src','modules','voices','experiments/vehicle_source_v1',
                   'tools/vehicle_controller','tools/vehicle_scenarios'):
        selected.update(p for p in (repo/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    selected.update(repo/name for name in ('Build-Vehicle-Source.ps1','tools/sound_designer/controller.py',
        'tools/startup_response_evidence_v1.py','tools/verify_startup_response_v1.py',
        'tools/verify_startup_response_ui_v1.py'))
    rows=[]
    for source in sorted(selected):
        name=source.relative_to(repo).as_posix();target=output/'exact_sources'/name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        rows.append(dict(path=name,sha256=sha(source)))
    binary=Path(binary) if binary is not None else repo/'build-vehicle-source-v6/bin/Release/vsl_source_bridge.dll'
    binding=dict(files=rows,bridge_path=binary.resolve().relative_to(repo.resolve()).as_posix(),bridge_sha256=sha(binary))
    (output/'source_binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2),encoding='utf-8')
    return binding


def verify(repo,binding):
    for row in binding['files']:assert sha(Path(repo)/row['path'])==row['sha256'],row['path']
    assert sha(Path(repo)/binding.get('bridge_path','build-vehicle-source-v4/bin/Release/vsl_source_bridge.dll'))==binding['bridge_sha256']
