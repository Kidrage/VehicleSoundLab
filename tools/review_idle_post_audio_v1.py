"""Export20same-gain listening files with one player after independent audit."""
import argparse
import json
import shutil
import sys
import urllib.request
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'audit', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_review.py')
r = dict(result='running', clips=[], inputs={})
try:
    audit = load(a.audit/'report.json'); rendered = load(a.input/'report.json')
    assert audit['result'] == 'passed' and audit['input_report_sha256'] == sha(a.input/'report.json')
    assert rendered['result'] == 'finite_POST_idle_audio_pending_listening'
    paths = {f'reference_{part}': a.input/f'reference_{part}.wav' for part in ['training', 'check']}
    for row in rendered['renders']:
        for bus in ['mix', 'detail']:
            paths[f"{row['method']}_{row['seed']}_{bus}"] = a.input/row['buses'][bus]['file']
    audio = {}
    for key, path in paths.items():
        audio[key], rate = sf.read(path, always_2d=True); assert rate == 48000
        r['inputs'][key] = dict(path=str(path), sha256=sha(path))
    gain = min(1., .85/max(abs(x).max() for x in audio.values())); files = {}
    fade = np.sin(np.linspace(0, np.pi/2, 1024))**2
    for key, x in audio.items():
        y = x.copy()*gain; y[:1024] *= fade[:, None]; y[-1024:] *= fade[::-1, None]
        path = a.out/(key+'.wav'); sf.write(path, y, 48000, subtype='PCM_24')
        actual, rate = sf.read(path, always_2d=True); error = float(abs(actual-y).max())
        assert rate == 48000 and error <= 2**-23 and abs(actual).max() <= .85+2**-23
        with urllib.request.urlopen('http://127.0.0.1:8789/'+path.relative_to(a.workspace).as_posix(), timeout=10) as response:
            assert response.read() == path.read_bytes()
        files[key] = path.name
        r['clips'].append(dict(key=key, frames=len(y), sha256=sha(path), max_quantization_error_FS=error))
    template = repo/'tools/idle_post_audio_v1/review.html'
    page = template.read_text(encoding='utf-8').replace('__GAIN__', format(gain, '.6g')).replace('__FILES__', json.dumps(files, separators=(',', ':')))
    (a.out/'index.html').write_text(page, encoding='utf-8'); shutil.copy2(template, a.out/'executed_template.html')
    assert page.count('<audio ') == 1 and '__FILES__' not in page and len(files) == 20
    url = 'http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url, timeout=10) as response: assert response.read() == (a.out/'index.html').read_bytes()
    r.update(result='single_player_POST_idle_review', common_gain=float(gain), files=files, url=url,
             input_report_sha256=sha(a.input/'report.json'), audit_sha256=sha(a.audit/'report.json'),
             listening_accepted=False, runtime_changed=False)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(dict(url=r.get('url'), common_gain=r.get('common_gain'), clips=len(r['clips'])), flush=True)
