"""Copy six frozen local anchors without refitting; bind their provenance."""
import argparse
from pathlib import Path
import shutil
from research_archive_v1 import load, save, sha

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
parent = a.workspace/'baselines/F3_local_atlas_v1'
manifest = load(parent/'manifest.json')
hashes = {v['path']: v['sha256'] for v in manifest['files']}
old = load(parent/'inputs/voice_files_sha256.json')
assert len(old) == 76 and all(sha(repo/n) == h for n, h in old.items())
dest = repo/'voices/F3_fifth_local_v1'
dest.mkdir(parents=True, exist_ok=False)
e = a.workspace/'references/analysis/catalog_local_F3_v1'
e.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, e/'executed_prepare.py')
for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
    shutil.copy2(parent/'inputs'/filename, e/('before_'+filename))
rows = []
for i, group in enumerate(('first', 'second'), 1):
    for j, point in enumerate(('early', 'mid', 'late'), 1):
        name = 'inputs/models/bank%d_anchor%d.model' % (i, j)
        source = parent/name
        assert sha(source) == hashes[name]
        path = dest/(group+'_'+point+'.model')
        shutil.copy2(source, path)
        assert sha(path) == hashes[name]
        header = path.read_text(encoding='utf-8').split()
        assert header[0] == 'VSL_SOUND_DNA' and int(header[5]) == 288 and int(header[6]) == 12
        rows.append(dict(path=path.relative_to(repo).as_posix(), parent_path=name,
                         sha256=sha(path), group=group, point=point, root_hz=float(header[7])))
report = dict(result='six_frozen_local_profiles_copied_exactly',
              parent='F3_local_atlas_v1', parent_manifest_sha256=sha(parent/'manifest.json'),
              original_76_voice_files_exact=True, source_refit=False, profiles=rows)
save(dest/'index.json', report)
save(e/'asset_provenance.json', report)
print('Six exact frozen profile copies ready;76 old voice files exact')
