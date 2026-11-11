"""Small three-view listening UI and explicitly boosted mechanical solos."""
import json
from runtime_review import ROOT, sha
import numpy as np
import soundfile as sf

OUT = ROOT/'renders/source_audition_v1'
PAGE = ROOT/'research/声源分层试听V1.html'


def main():
    if (OUT/'verification.json').exists() or (ROOT/'baselines/source_audition_v1').exists():
        raise SystemExit('Preserve completed source-audition page.')
    result = json.loads((OUT/'results.json').read_text())
    data = result['page_data']
    boosted = {}
    boost = 10**(24/20)
    for scene, row in data.items():
        row['mechanical_boost'] = {}
        for recipe in result['recipe_labels']:
            key = f'{scene}_{recipe}'
            x, sr = sf.read(OUT/f'{key}_solo_mechanical.wav', always_2d=True)
            x *= 10**(row['gain_db']/20)*boost
            assert sr == 48000 and np.isfinite(x).all() and abs(x).max() < .85
            path = OUT/f'audition_{key}_mechanical_plus24.wav'
            sf.write(path, x, sr, subtype='PCM_24')
            row['mechanical_boost'][recipe] = '../renders/source_audition_v1/'+path.name
            boosted[key] = dict(file=path.name, sha256=sha(path), extra_gain_db=24,
                total_gain_db=row['gain_db']+24, peak=float(abs(x).max()),
                processing='Explicit optional +24 dB mechanical solo only. Same constant extra gain for every scene/recipe. Default off; reset on leaving mechanical solo. No normalization/compression.')
    values = dict(DATA=data, RECIPES=result['recipe_labels'], GROUPS=result['group_labels'], REFERENCES=result['references'])
    template = ROOT/'tools/source_audition_page.html'
    html = template.read_text(encoding='utf-8')
    for name, value in values.items():
        html = html.replace('__'+name+'__', json.dumps(value, ensure_ascii=False).replace('</', '<\\/'))
    assert not any('__'+name+'__' in html for name in values)
    PAGE.write_text(html, encoding='utf-8')
    report = dict(result='pass', base_results_sha256=sha(OUT/'results.json'), page_data=data,
        optional_mechanical_boost=boosted, references=result['references'],
        page=PAGE.relative_to(ROOT).as_posix(), page_sha256=sha(PAGE),
        source_files={p.relative_to(ROOT).as_posix():sha(p) for p in [template, ROOT/'tools/make_source_audition_page.py']},
        scope='Existing frozen sound only. Mechanical auxiliary gain is explicit and never applied to full/remove views. Browser switching preserves requested time/state but is not sample-accurate or gapless.')
    (OUT/'page.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(result='pass', page=str(PAGE), auditions=120, optional_boosted_mechanical_solos=8), ensure_ascii=False))


if __name__ == '__main__':
    main()
