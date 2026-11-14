"""One-player triplet versus mid-only review, common gain and no new source fit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import urllib.request
from research_archive_v1 import load, save, sha
p = argparse.ArgumentParser(description=__doc__)
for k in ('workspace', 'out'):
    p.add_argument('--'+k, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[k] = '2'
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
a.out.mkdir(parents=True, exist_ok=False)
study = a.workspace/'references/analysis/F3_local_atlas_v1'
r = dict(result='running', sources={}, inputs={}, banks=[], clips=[], gain=.5, fade_frames=240, hearing=False)
try:
    source = load(study/'source1/report.json')
    assert load(study/'audit1/report.json')['result'] == 'two_local_atlas_dynamic_clocks_alignment_and_sparse_C_verified'
    for i, bank in enumerate(source['banks'], 1):
        key = 'bank%d' % i
        r['banks'].append(dict(key=key, name=bank['name'], title='五挡第%s次升速' % ('一' if i == 1 else '二'), roots=bank['root_hz']))
        for row in bank['renders']:
            raw = study/'source1'/bank['name']/row['file']
            assert sha(raw) == row['sha256']
            r['inputs'][str(raw)] = sha(raw)
            x, rate = sf.read(raw, always_2d=True)
            assert x.shape == (576000, 2) and rate == 48000
            y = x*.5
            fade = .5-.5*np.cos(np.pi*np.arange(240)/240)
            y[:240] *= fade[:, None]
            y[-240:] *= fade[::-1, None]
            assert np.isfinite(y).all() and abs(y).max() < .95
            name = '%s_%s_%d' % (key, row['variant'], row['seed'])
            dest = a.out/(name+'.wav')
            sf.write(dest, y, 48000, subtype='FLOAT')
            saved, rate = sf.read(dest, always_2d=True)
            assert np.array_equal(saved, y.astype('float32').astype(float))
            variant = '三锚点过渡' if row['variant'] == 'triplet' else '单中点变调'
            generation = (1, 23117, 61927).index(row['seed'])+1
            r['clips'].append(dict(key=name, bank_key=key, variant=row['variant'], seed=row['seed'],
                title='%s · 生成%d' % (variant, generation), note='%s，12秒持续生成，细节序列%d。' % (variant, row['seed']),
                file=dest.name, frames=len(saved), sha256=sha(dest), peak_FS=float(abs(saved).max())))
    for n in ('source1/report.json', 'audit1/report.json', 'audit1/diagnostic.png'):
        r['inputs'][str(study/n)] = sha(study/n)
    shutil.copy2(study/'audit1/diagnostic.png', a.out/'diagnostic.png')
    save(a.out/'data.json', dict(banks=r['banks'], clips=r['clips']))
    template = repo/'tools/F3_local_atlas_v1/review.html'
    (a.out/'index.html').write_text(template.read_text(encoding='utf-8').replace('__DATA__',
        (a.out/'data.json').read_text(encoding='utf-8')), encoding='utf-8', newline='\n')
    for n in ('tools/F3_local_atlas_v1/review.html', 'tools/review_F3_local_atlas_v1.py'):
        dest = a.out/'exact_sources'/n
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/n, dest)
        r['sources'][n] = sha(repo/n)
    r['url'] = 'http://127.0.0.1:8789/'+a.out.relative_to(a.workspace).as_posix()+'/index.html'
    for n in ['index.html', 'data.json', 'diagnostic.png']+[v['file'] for v in r['clips']]:
        with urllib.request.urlopen(r['url'].rsplit('/', 1)[0]+'/'+n, timeout=10) as response:
            assert response.read() == (a.out/n).read_bytes()
    r.update(result='two_local_atlas_one_player_review_ready', fixed_gain=True, per_clip_normalization=False,
             room=False, new_timbre_accepted=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(dict(result=r['result'], clips=len(r['clips']), url=r.get('url')))
