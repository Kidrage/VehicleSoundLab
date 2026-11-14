"""Publish five native/common-root comparisons, one player and one common gain."""
import argparse
import os
from pathlib import Path
import shutil
import sys
import urllib.request
from research_archive_v1 import load, save, sha

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'out'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf

study = a.workspace/'references/analysis/F3_pitch_anchors_v1'
a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, clips=[], cases=[], gain=.5,
         fade_frames=240, room=False, hearing=False, runtime_changed=False)
try:
    fit = load(study/'fit1/report.json')
    audit = load(study/'audit1/report.json')
    compare = load(study/'compare1/report.json')
    assert fit['qualified'] == 5 and fit['excluded'] == 0
    assert audit['result'] == 'fixed_F3_pitch_anchors_audited'
    assert compare['result'] == 'five_F3_common_pitch_descriptive_comparisons_complete'
    titles = ['五挡第一段 · 前部', '五挡第一段 · 后部', '五挡第二段 · 前部',
              '五挡第二段 · 后部', '六挡升速 · 前部']
    for index, (row, checked, compared) in enumerate(zip(fit['cases'], audit['cases'], compare['cases']), 1):
        case = row['case']
        assert case['name'] == checked['name'] == compared['name']
        case_key = 'case%d' % index
        root = row['extraction']['root_hz']
        r['cases'].append(dict(key=case_key, name=case['name'], title=titles[index-1],
                               seconds=case['seconds'], root_hz=root))
        native = study/'fit1'/case['name']
        common = study/'compare1'/case['name']
        items = [('native', 'original', native/'native.wav', '原录音 · 保留升速',
                  '获批F3录音的原生短片段，保留原有升速与双声道。'),
                 ('native', 'reference', native/'reference.wav', '固定音高参考 · 短片段',
                  '同一局部录音的固定音高参考，声学根频率%.2f Hz。' % root),
                 ('common', 'reference', common/'reference64.wav', '固定音高参考 · 64 Hz',
                  '同一局部录音统一到64 Hz的短参考，保留双声道。')]
        for mode, folder, prefix in [('native', native, 'DNA'), ('common', common, 'DNA64')]:
            for generation, seed in enumerate((1, 23117, 61927), 1):
                hz = root if mode == 'native' else 64
                items.append((mode, 'seed%d' % seed, folder/('%s_%d.wav' % (prefix, seed)),
                              '持续主声线 · 生成%d' % generation,
                              '持续生成8秒，声学根频率%.2f Hz，细节序列%d。' % (hz, seed)))
        for mode, kind, source, title, note in items:
            r['inputs'][str(source)] = sha(source)
            x, rate = sf.read(source, always_2d=True)
            assert rate == 48000 and x.shape[1] == 2 and len(x) > 480
            y = x*r['gain']
            fade = .5-.5*np.cos(np.pi*np.arange(240)/240)
            y[:240] *= fade[:, None]
            y[-240:] *= fade[::-1, None]
            assert np.isfinite(y).all() and abs(y).max() < .95
            key = '_'.join((case_key, mode, kind))
            dest = a.out/(key+'.wav')
            sf.write(dest, y, rate, subtype='FLOAT')
            saved, rate = sf.read(dest, always_2d=True)
            assert rate == 48000 and np.array_equal(saved, y.astype('float32').astype(float))
            r['clips'].append(dict(key=key, case_key=case_key, mode=mode, kind=kind,
                                   file=dest.name, title=title, note=note, frames=len(saved),
                                   source_sha256=sha(source), sha256=sha(dest), peak_FS=float(abs(saved).max())))
    assert len(r['clips']) == 45
    for name in ('fit1/report.json', 'audit1/report.json', 'compare1/report.json', 'compare1/comparison.png'):
        r['inputs'][str(study/name)] = sha(study/name)
    shutil.copy2(study/'compare1/comparison.png', a.out/'comparison.png')
    save(a.out/'data.json', dict(cases=r['cases'], clips=r['clips']))
    template = repo/'tools/F3_pitch_anchors_v1/review.html'
    html = template.read_text(encoding='utf-8').replace('__DATA__', (a.out/'data.json').read_text(encoding='utf-8'))
    (a.out/'index.html').write_text(html, encoding='utf-8', newline='\n')
    for name in ('tools/review_F3_pitch_anchors_v1.py', 'tools/F3_pitch_anchors_v1/review.html'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    r['url'] = 'http://127.0.0.1:8789/'+a.out.relative_to(a.workspace).as_posix()+'/index.html'
    for name in ['index.html', 'data.json', 'comparison.png']+[v['file'] for v in r['clips']]:
        with urllib.request.urlopen(r['url'].rsplit('/', 1)[0]+'/'+name, timeout=10) as response:
            assert response.read() == (a.out/name).read_bytes()
    r.update(result='five_F3_native_and_common_root_review_ready', fixed_common_gain=True,
             per_clip_normalization=False, PCM_loop_synthesis=False, physical_RPM_or_load=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(dict(result=r['result'], clips=len(r['clips']), url=r.get('url')))
