"""Snapshot the current original C baseline without modifying previous versions."""
import sys
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import importlib.metadata
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
version='v0.1.0';folder=ROOT/'baselines'/version
if folder.exists():raise SystemExit('Baseline already exists; preserve it and create a new version for voicing changes.')
folder.mkdir(parents=True)
shutil.copytree(ROOT/'src',folder/'src')
shutil.copytree(ROOT/'tests',folder/'tests')
shutil.copyfile(ROOT/'CMakeLists.txt',folder/'CMakeLists.txt')
files=[]
for name,pure in [('v10_pure_osc.wav',True),('v10_three_layers.wav',False)]:
    original=ROOT/'renders'/name;copy=folder/name
    command=[str(ROOT/'build/Release/vsl_render.exe'),str(copy)]
    if pure:command.append('--pure')
    subprocess.run(command,check=True,capture_output=True)
    old=hashlib.sha256(original.read_bytes()).hexdigest();new=hashlib.sha256(copy.read_bytes()).hexdigest()
    if old!=new:raise RuntimeError('Baseline render changed unexpectedly: '+name)
    files.append(dict(path=name,sha256=new))
for path in sorted(list((folder/'src').rglob('*'))+list((folder/'tests').rglob('*'))+[folder/'CMakeLists.txt']):
    if path.is_file():files.append(dict(path=str(path.relative_to(folder)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
manifest=dict(version=version,sample_rate=48000,seed=48271,drive_seconds=12,
    status='Engineering oscillator baseline; reference calibration pending',files=files)
(folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
packages={name:importlib.metadata.version(name) for name in ('numpy','scipy','matplotlib','soundfile','yt-dlp')}
(ROOT/'research/python_environment.json').write_text(json.dumps(dict(python=sys.version,packages=packages,
    dependency_location=str(ROOT/'tools/python_deps'),ffmpeg=subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0]),indent=2),encoding='utf-8')
print('Frozen baseline, repeated WAV hashes agree:',folder)
