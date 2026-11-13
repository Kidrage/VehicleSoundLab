"""Independent complete audio, all38 native curves and immutable-runtime check."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load, save, sha
from idle_post_audio_v1.independent import Random, native_power, modal, texture, filter_polynomial, curves, direct, PAIRS

a.out.mkdir(parents=True, exist_ok=False); shutil.copy2(__file__, a.out/'executed_auditor.py')
shutil.copy2(repo/'tools/idle_post_audio_v1/independent.py', a.out/'executed_independent.py')
r = dict(result='running', max_wave_error_FS=0., max_filter_error_FS=0., max_curve_error=0.,
         max_direct_error=0., all_curve_values=0)
try:
    observed = load(a.input/'report.json'); assert observed['result'] == 'finite_POST_idle_audio_pending_listening'
    for name, digest in observed['sources'].items(): assert digest == sha(repo/name) == sha(a.input/'exact_sources'/name)
    tables = {}
    for name, digest in observed['parent_manifests'].items():
        path = a.workspace/'baselines'/name/'manifest.json'; assert sha(path) == digest
        tables[name] = {v['path']: v['sha256'] for v in load(path)['files']}
    for path, digest in observed['inputs'].items():
        rel = Path(path).relative_to(a.workspace/'baselines')
        assert sha(path) == digest == tables[rel.parts[0]][Path(*rel.parts[1:]).as_posix()]
    lags = np.arange(-1920, 1921, 48)

    def compare(x, data, direct_check=False):
        oracle = curves(x, lags)
        for name in ['cumulant', 'normalized', 'variance', 'normalized_covariance']:
            error = float(abs(oracle[name]-data[name]).max())
            r['max_curve_error'] = max(r['max_curve_error'], error)
            assert np.allclose(oracle[name], data[name], rtol=1e-8, atol=1e-10), (name, error)
        if direct_check:
            error = float(abs(direct(x, lags)-oracle['normalized']).max())
            r['max_direct_error'] = max(r['max_direct_error'], error); assert error < 1e-8
        r['all_curve_values'] += 810

    for name in ['delayed_common', 'slow_common_amplitude']:
        with np.load(a.input/'known'/(name+'.npz')) as z:
            compare(z['audio'], z, True)
            if name == 'delayed_common':
                assert np.array_equal(z['audio'][96:, 1], z['audio'][:-96, 0])
                assert lags[np.argmax(z['normalized'][PAIRS.index((0, 1))])] == 96
    print(dict(stage='independent_known_pass'), flush=True)
    profile = load(observed['profile_path']); law = load(observed['law_path'])['observations'][0]['models']['expanded']
    old_p = load(observed['old_path'])['probability']; kappa = np.asarray(load(observed['new_path'])['allocation']['kappa'])
    new_p = 3/(kappa+3); assert np.array_equal(new_p, observed['new_probability'])
    frames = 576000; main = modal(profile, frames); q = native_power(profile, law, frames)
    r['native_q_error'] = float(abs(q-np.load(a.input/'native_q.npy')).max()); assert r['native_q_error'] < 1e-10
    r['main_wave_error_FS'] = float(abs(main-sf.read(a.input/'main.wav', always_2d=True)[0]).max())
    assert r['main_wave_error_FS'] < 2e-8
    for seed in [149921, 277139, 381611]:
        outputs = texture(profile, old_p, new_p, q, seed, frames)
        for method, detail in outputs.items():
            row = next(z for z in observed['renders'] if z['method'] == method and z['seed'] == seed)
            for bus, expected in [('mix', main+detail), ('detail', detail)]:
                path = a.input/row['buses'][bus]['file']; assert sha(path) == row['buses'][bus]['sha256']
                actual, rate = sf.read(path, always_2d=True); error = float(abs(actual-expected).max())
                r['max_wave_error_FS'] = max(r['max_wave_error_FS'], error)
                assert rate == 48000 and error < 2e-8 and np.isfinite(actual).all() and abs(actual).max() < 1.
                if method in ['static', 'sparse']:
                    tag = '000' if method == 'static' else '100'
                    old = a.workspace/f'baselines/idle_excitation_moments_v1/evidence/trial1/{bus}_{tag}_{seed}.wav'
                    assert np.array_equal(actual, sf.read(old, always_2d=True)[0])
                    if method == 'static' and bus == 'mix':
                        old = a.workspace/f'baselines/idle_texture_v2/evidence/trial1/fine_{seed}.wav'
                        assert np.array_equal(actual, sf.read(old, always_2d=True)[0])
        print(dict(stage='independent_full_wave_pass', seed=seed), flush=True)
    sos = np.load(a.input/'sos.npy'); cache = {}; results = []
    for row in observed['observations']:
        assert sha(a.input/row['file']) == row['sha256']
        with np.load(a.input/row['file']) as z: data = {key: z[key] for key in z.files}
        assert np.array_equal(data['lags'], lags)
        if 'source_path' in row:
            with np.load(row['source_path']) as z: audio = z['audio']
            filtered = filter_polynomial(audio[:, 0], sos)[4800:-4800]
            prior = a.workspace/f"baselines/idle_joint_lag_v1/evidence/observe1/{row['label']}.npz"
            with np.load(prior) as z: assert np.allclose(data['normalized'], z['raw_normalized'], atol=1e-9)
            assert np.array_equal(sf.read(a.input/('reference_'+row['label']+'.wav'), always_2d=True)[0], audio.astype(np.float32))
        else:
            key = row['audio_file']
            if key not in cache:
                audio, rate = sf.read(a.input/key, always_2d=True); assert rate == 48000
                cache = {key: filter_polynomial(audio[:, 0], sos)}
            block = row['block']; filtered = cache[key][block*144000+4800:(block+1)*144000-4800]
        error = float(abs(filtered-data['filtered']).max()); r['max_filter_error_FS'] = max(r['max_filter_error_FS'], error)
        assert error < 1e-10
        compare(filtered, data, 'source_path' in row)
        results.append(row['label'])
    assert len(results) == 38 and r['all_curve_values'] == 40*810
    counts = {}
    for name, count in [('C_files_sha256.json', 612), ('voice_files_sha256.json', 67)]:
        values = load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name); assert len(values) == count
        for path, digest in values.items(): assert sha(repo/path) == digest, path
        counts[name] = count
    r.update(result='passed', input_report_sha256=sha(a.input/'report.json'),
             complete_buses=18, all_real_observations=results, invariant_counts=counts,
             baseline_all12_buses_exact=True, runtime_changed=False, listening_accepted=False)
except Exception as exc: r.update(result='failed', error=repr(exc)); raise
finally: save(a.out/'report.json', r)
print(r, flush=True)
