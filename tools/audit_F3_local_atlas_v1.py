"""Check dynamic clocks, alignment, branch crossings and sparse stochastic output."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha
p = argparse.ArgumentParser(description=__doc__)
for name in ('workspace', 'source', 'out'):
    p.add_argument('--'+name, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[k] = '2'
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from idle_texture_v1.profile import load as model_load
from local_atlas_v1.oracle import clock, alignment, selection, sparse

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, banks=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


try:
    for n in ['tools/audit_F3_local_atlas_v1.py', 'tools/local_atlas_v1/oracle.py',
              'tools/sustain_osc_v1/oracle.py', 'tools/idle_texture_v1/profile.py']:
        dest = a.out/'exact_sources'/n
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/n, dest)
        r['sources'][n] = sha(repo/n)
    source = load(consume(a.source/'report.json'))
    assert source['result'] == 'two_separate_frozen_triplets_rendered'
    for n, digest in source['sources'].items():
        assert sha(repo/n) == digest == sha(a.source/'exact_sources'/n)
    for n, digest in source['inputs'].items():
        assert sha(consume(Path(n))) == digest
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout='constrained')
    for b, bank in enumerate(source['banks']):
        folder = a.source/bank['name']
        models = [model_load(consume(Path(n)))[0] for n in bank['models']]
        events = np.loadtxt(consume(folder/'trajectory.trace'), skiprows=1)
        roots, phases, end_phase = clock(events, 576000)
        base = np.array(bank['root_hz'])
        lo, hi, blend, coverage = selection(roots, base)
        changes = np.flatnonzero((lo[1:] != lo[:-1]) | (hi[1:] != hi[:-1]))+1
        indices = {0, 1, 239, 240, 511, 512, 4800, 11999, 47999, 95999, 191999, 383999, 575999}
        for n in list(changes)+[48000, 192000, 240000, 384000, 432000, 528000]:
            indices.update(range(max(0, n-3), min(576000, n+4)))
        indices = sorted(indices)
        row = dict(name=bank['name'], branch_changes=changes.tolist(), sparse_indices=indices, renders=[])
        offsets = load(consume(folder/'triplet_1.json'))['offsets']
        row['alignment'] = alignment(models, offsets)
        for clip in bank['renders']:
            prefix = folder/clip['file']
            wave, rate = sf.read(consume(prefix), always_2d=True)
            assert sha(prefix) == clip['sha256'] and rate == 48000 and wave.shape == (576000, 2)
            meta = load(consume(prefix.with_suffix('.json')))
            csv = np.genfromtxt(consume(prefix.with_suffix('.csv')), delimiter=',', names=True)
            locations = csv['frame'].astype(int)
            assert len(np.unique(locations)) == len(locations) and locations[0] == 0 and locations[-1] == 575999
            assert set(changes).issubset(locations) if clip['variant'] == 'triplet' else True
            root_error = float(abs(csv['root_hz']-roots[locations]).max())
            phase_error = float(abs(csv['phase_in']-phases[locations]).max())
            after = np.r_[phases[1:], end_phase]
            phase_after_error = float(abs(csv['phase_out']-after[locations]).max())
            assert max(root_error, phase_error, phase_after_error) < 1e-10
            if clip['variant'] == 'triplet':
                chosen, chosen_base, chosen_offsets = models, base, offsets
                assert meta['offsets'] == offsets
                expected_lo, expected_hi, expected_blend, expected_coverage = lo, hi, blend, coverage
            else:
                chosen, chosen_base, chosen_offsets = models[1:2], base[1:2], [0.]
                expected_lo, expected_hi, expected_blend, expected_coverage = selection(roots, chosen_base)
            assert np.array_equal(csv['lower'], expected_lo[locations])
            assert np.array_equal(csv['upper'], expected_hi[locations])
            assert np.array_equal(csv['coverage'], expected_coverage[locations])
            assert abs(csv['blend']-expected_blend[locations]).max() < 1e-12
            expected, updates = sparse(chosen, chosen_base, chosen_offsets, clip['seed'], roots, phases, indices)
            error = abs(wave[indices]-expected)
            tolerance = .5001*np.spacing(abs(expected.astype('float32'))).astype(float)+2e-9
            assert np.all(error <= tolerance), (bank['name'], clip, float((error-tolerance).max()))
            assert meta['texture_updates'] == [updates]*len(chosen) and meta['source_frame'] == 576000
            row['renders'].append(dict(variant=clip['variant'], seed=clip['seed'], csv_rows=len(csv),
                                      root_error_hz=root_error, phase_error_rad=max(phase_error, phase_after_error),
                                      sparse_points=len(indices), maximum_error_FS=float(error.max()),
                                      maximum_excess_FS=float((error-tolerance).max()), texture_updates=updates))
            print('PASS sparse dynamic C', bank['name'], clip['variant'], clip['seed'], flush=True)
        row['coverage_all_samples'] = dict(below=int((coverage < 0).sum()), inside=int((coverage == 0).sum()), above=int((coverage > 0).sum()))
        # Purely descriptive generated L/R powers; no original-vs-C realism gate.
        raw, _ = sf.read(folder/'triplet_1.wav', always_2d=True)
        mid, _ = sf.read(folder/'mid_1.wav', always_2d=True)
        blocks = 2400
        lp = np.mean(raw.reshape(-1, blocks, 2)**2, axis=1)
        mp = np.mean(mid.reshape(-1, blocks, 2)**2, axis=1)
        times = np.arange(len(lp))*.05+.025
        axes[0, b].plot(np.arange(0, len(roots), 240)/48000, roots[::240], label='Smoothed acoustic root')
        axes[0, b].plot(events[:, 0]/48000, events[:, 1], '--', label='Engineering target')
        for x in base:
            axes[0, b].axhline(x, color='gray', lw=.7, alpha=.6)
        axes[0, b].set(title=bank['name'], ylabel='Acoustic root / Hz', xlabel='Seconds')
        axes[0, b].legend(fontsize=8)
        for c, name in enumerate(('L', 'R')):
            axes[1, b].plot(times, 10*np.log10(lp[:, c]/mp[:, c]), label=name)
        axes[1, b].set(ylabel='Triplet minus mid-only power / dB', xlabel='Seconds')
        axes[1, b].legend()
        row['generated_power_difference_db_range'] = [float(np.min(10*np.log10(lp/mp))), float(np.max(10*np.log10(lp/mp)))]
        r['banks'].append(row)
        save(a.out/'report.json', r)
    fig.suptitle('Separate F3 local banks; same voice/trace; descriptive only, no listening acceptance')
    fig.savefig(a.out/'diagnostic.png', dpi=140)
    plt.close(fig)
    original = load(consume(a.workspace/'baselines/bandlimited_dna_v1/inputs/C_files_sha256.json'))
    voices = load(consume(a.workspace/'baselines/bandlimited_dna_v1/inputs/voice_files_sha256.json'))
    assert len(original) == 656 and len(voices) == 76
    assert all(sha(repo/n) == digest for n, digest in {**original, **voices}.items())
    r.update(result='two_local_atlas_dynamic_clocks_alignment_and_sparse_C_verified',
             C_H_prior_exact=656, voices_exact=76, full_wave_stochastic_oracle=False,
             original_source_RPM_or_load_calibrated=False, new_timbre_acceptance=False,
             physical_7_1_4=False, no_source_refit=True, shared_DSP_changed=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(r['result'], flush=True)
