"""Frozen C takes -> spatial source-group auditions, without changing voicing."""
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from runtime_review import ROOT, sha, rms
import numpy as np
import soundfile as sf

OUT = ROOT/'renders/source_audition_v1'
PROBE = ROOT/'build-experiment-source-audition/Release/source_audition_probe.exe'
CASES = {'mid': '4000 RPM · 带载', 'high': '8000 RPM · 带载',
         'neutral': '空挡补油与落转', 'drive': '30 秒运动自动挡'}
RECIPES = {'base': '原声基线', 'combined': '既有细节 · 燃烧／机械各 65%'}
GROUPS = {'exhaust': '排气', 'body': '机体／IR 返回', 'mechanical': '机械',
          'intake': '进气', 'air': '气流', 'events': '瞬态事件', 'road_wind': '路噪／风噪'}


def read(path):
    x, sr = sf.read(path, always_2d=True)
    assert sr == 48000 and sf.info(path).subtype == 'FLOAT' and np.isfinite(x).all(), path
    return x


def validate(prefix, native=None):
    meta = json.loads(Path(str(prefix)+'_groups.json').read_text())
    assert meta['schema'] == 'vsl.source-audition/1' and meta['base_runtime'] == '0.16.0'
    assert [g['name'] for g in meta['groups']] == list(GROUPS)
    masks = [g['mask'] for g in meta['groups']]
    assert sum(masks) == (1 << 10)-1
    assert all(a & b == 0 for i, a in enumerate(masks) for b in masks[i+1:])
    modes = [m['name'] for m in meta['modes']]
    assert modes == ['full']+[f'{view}_{g}' for g in GROUPS for view in ['solo','without']]
    assert all(m['clipped_samples'] == 0 for m in meta['modes'])
    full = read(Path(str(prefix)+'_full.wav'))
    assert np.max(abs(full)) < .95
    if native:
        assert sha(Path(str(prefix)+'_full.wav')) == sha(native.with_suffix('.wav'))
        assert sha(prefix.with_suffix('.csv')) == sha(native.with_suffix('.csv'))
    summed = np.zeros_like(full)
    closure, levels = {}, {'full': rms(full)}
    for group in GROUPS:
        solo = read(Path(str(prefix)+'_solo_'+group+'.wav'))
        without = read(Path(str(prefix)+'_without_'+group+'.wav'))
        assert solo.shape == without.shape == full.shape
        assert max(float(abs(solo).max()), float(abs(without).max())) < .95
        error = float(abs(solo+without-full).max())
        assert error < 2e-7, (prefix, group, error)
        closure[group] = error
        summed += solo
        levels['solo_'+group] = rms(solo)
        levels['without_'+group] = rms(without)
    error = float(abs(summed-full).max())
    assert error < 2e-7
    scene = json.loads(Path(str(prefix)+'_scene.json').read_text())
    assert scene['channels'] == (['FL','FR'] if full.shape[1] == 2 else
        ['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR'])
    assert len(scene['objects']) == 10
    for obj in scene['objects']:
        path = Path(obj['file'])
        assert path.is_file() and read(path).shape == (len(full), 1)
    return dict(frames=len(full), channels=full.shape[1], sum_groups_max_error=error,
                complement_max_errors=closure, rms_dbfs=levels,
                group_metadata_sha256=sha(Path(str(prefix)+'_groups.json')),
                scene_metadata_sha256=sha(Path(str(prefix)+'_scene.json')))


def main():
    if OUT.exists():
        raise SystemExit('Preserve source_audition_v1; output folder already exists.')
    OUT.mkdir()
    native = json.loads((ROOT/'renders/v0.16.0/verification.json').read_text())
    inputs = {}
    for case in CASES:
        for recipe in RECIPES:
            for ext in ['vsltake', 'wav', 'csv']:
                path = ROOT/f'renders/v0.16.0/{case}_{recipe}.{ext}'
                assert sha(path) == native['files'][path.name]
                inputs[path.relative_to(ROOT).as_posix()] = sha(path)

    def render(name, channels):
        take = re.sub('_714$', '', name)
        args = [str(PROBE), str(ROOT/f'renders/v0.16.0/{take}.vsltake'), str(OUT/name), str(channels)]
        run = subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True, timeout=180)
        assert '| pass' in run.stdout
        print('rendered '+name, flush=True)
        return name, dict(command=args, stdout=run.stdout)

    commands = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(render, f'{case}_{recipe}', 2) for case in CASES for recipe in RECIPES]
        jobs.append(pool.submit(render, 'high_combined_714', 12))
        for job in as_completed(jobs):
            key, row = job.result();commands[key] = row
    rows, pages = {}, {}
    old_stems = {}
    for case in CASES:
        for recipe in RECIPES:
            key = f'{case}_{recipe}'
            rows[key] = validate(OUT/key, ROOT/f'renders/v0.16.0/{key}.vsltake')
            # Existing independent source exports cover four base cases and high character.
            old = 'high_character' if recipe == 'combined' and case == 'high' else case if recipe == 'base' else None
            if old:
                scene = json.loads((OUT/f'{key}_scene.json').read_text())
                for obj in scene['objects']:
                    previous = ROOT/f'renders/exhaust_phase_v1/{old}_base_source_{obj["name"]}.wav'
                    assert sha(previous) == sha(Path(obj['file']))
                    inputs[previous.relative_to(ROOT).as_posix()] = sha(previous)
                old_stems[key] = len(scene['objects'])

        # A single scene gain is shared by both recipes AND every listening view.
        # Full mixes set nominal RMS, all views constrain peak headroom.
        full_rms = max(rows[f'{case}_{r}']['rms_dbfs']['full'] for r in RECIPES)
        largest = max(float(abs(read(OUT/f'{case}_{r}_{m["name"]}.wav')).max())
                      for r in RECIPES for m in json.loads((OUT/f'{case}_{r}_groups.json').read_text())['modes'])
        gain = min(10**((-23-full_rms)/20), .85/largest)
        pages[case] = dict(label=CASES[case], gain_db=float(20*np.log10(gain)), takes={})
        for recipe in RECIPES:
            key = f'{case}_{recipe}';rows[key]['auditions'] = {};pages[case]['takes'][recipe] = {}
            for mode in json.loads((OUT/f'{key}_groups.json').read_text())['modes']:
                name = mode['name'];x = read(OUT/f'{key}_{name}.wav')*gain
                path = OUT/f'audition_{key}_{name}.wav'
                sf.write(path, x, 48000, subtype='PCM_24')
                rows[key]['auditions'][name] = dict(file=path.name, sha256=sha(path),
                    gain_db=pages[case]['gain_db'], peak=float(abs(x).max()), rms_dbfs=rms(x),
                    processing='One scene-wide fixed gain across both frozen recipes and all 15 views. PCM24; no fades, EQ, separate normalization or compression.')
                pages[case]['takes'][recipe][name] = '../renders/source_audition_v1/'+path.name

    rows['high_combined_714'] = validate(OUT/'high_combined_714')
    stereo_scene = json.loads((OUT/'high_combined_scene.json').read_text())
    for obj in stereo_scene['objects']:
        assert sha(OUT/f'high_combined_714_source_{obj["name"]}.wav') == sha(Path(obj['file']))
    assert sha(OUT/'high_combined_714.csv') == sha(OUT/'high_combined.csv')

    # Reuse already-approved, hash-bound manual reference derivatives unchanged.
    previous = json.loads((ROOT/'renders/exhaust_envelope_v1/results.json').read_text())
    reference = {}
    for name in ['low','blips']:
        path = ROOT/f'renders/exhaust_envelope_v1/reference_A_{name}.wav'
        assert sha(path) == previous['files'][path.name]
        inputs[path.relative_to(ROOT).as_posix()] = sha(path)
        reference[name] = dict(path='../renders/exhaust_envelope_v1/'+path.name, sha256=sha(path),
            processing='Existing unchanged approved A derivative: fixed -6.0206 dB gain, 5 ms cosine endpoints, PCM24. No level/state/microphone match to synthesizer.')
    log = ROOT/'build-experiment-source-audition/Testing/Temporary/LastTest.log'
    assert 'Test Passed.' in log.read_text(errors='replace')
    shutil.copy2(log, OUT/'ctest_original.log')
    sources = [ROOT/'tools/render_source_audition.py', *sorted((ROOT/'experiments/source_audition_v1').glob('*')),
        ROOT/'build-experiment-source-audition/audition_engine.c', ROOT/'build-experiment-source-audition/audition_scene.c',
        ROOT/'build-experiment-source-audition/audition_take.c']
    binary = [PROBE, ROOT/'build-experiment-source-audition/Release/source_audition_checks.exe',
              ROOT/'build-experiment-source-audition/Release/source_audition.lib', ROOT/'build-v016/Release/vsl_core.lib']
    result = dict(schema='vsl.source-audition-review/1', runtime='0.16.0 unchanged', cases=rows,
        page_data=pages, recipe_labels=RECIPES, group_labels=GROUPS, references=reference, inputs=inputs,
        existing_source_exports_exact=old_stems, commands=commands,
        stereo_714_source_and_trace_identity=True,
        source_files={p.relative_to(ROOT).as_posix():sha(p) for p in sources if p.is_file()},
        binaries={p.relative_to(ROOT).as_posix():sha(p) for p in binary},
        files={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        interpretation='Acoustic-object listening views after source construction and IR. Full native mix unchanged. Removing exhaust objects retains exhaust-driven body IR. Not excitation ablation, new voicing or realism acceptance.')
    (OUT/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(result='pass', stereo_takes=8, views_per_take=15, auditions=120,
        layout12_check=True, unchanged_old_source_exports=old_stems), indent=2))


if __name__ == '__main__':
    main()
