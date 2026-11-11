"""Fetch pinned textual source for inspection; never fetch upstream audio."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
REV = 'ac2b37d8639027d79934a2023cf8d1d37d3b2f96'
FILES = ['README.md', 'SOUND_DESIGN_GUIDE.md', '.codex/REPO_GUIDE.md',
         'gen/ioniq6n_powertrain.gendsp', 'gen/v10_powertrain.gendsp',
         'presets/sound_dna.json', 'assets/ioniq6n_acoustic_targets.json',
         'presets/ioniq6n_soundscape_modes_factory.json',
         'patchers/ioniq6n_sound_dna~.maxpat', 'patchers/v10_sound_dna~.maxpat',
         'patchers/mix_master~.maxpat', 'tools/build_project.py',
         'tools/audio_metrics.py', 'tools/validate_v10_lifecycle.py']

def fetch(name):
    destination = ROOT / 'research/upstream' / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = urllib.request.urlopen('https://raw.githubusercontent.com/Kidrage/VehicleSoundSynth/' + REV + '/' + name, timeout=30).read()
    destination.write_bytes(data)
    return dict(path=name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(fetch, FILES))
    (ROOT / 'research/upstream_snapshot.json').write_text(json.dumps(dict(revision=REV, files=results), indent=2), encoding='utf-8')
    print('Fetched', len(results), 'text source files. No audio fetched.')
