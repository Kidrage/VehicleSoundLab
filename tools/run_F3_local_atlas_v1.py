"""Known controls first, then frozen triplets through one existing SaVoice."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load, save, sha
p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'out', 'build'):
    p.add_argument('--'+key, type=Path, required=True)
p.add_argument('--stage', choices=('known', 'source'), required=True)
p.add_argument('--known', type=Path)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from local_atlas_v1.inputs import manifest, trace
from local_atlas_v1.oracle import clock, alignment
from idle_texture_v1.profile import load as model_load

a.out.mkdir(parents=True, exist_ok=False)
study = a.workspace/'references/analysis/F3_local_atlas_v1'
build = repo/'build-local-atlas-v1/bin/Release'
probe = build/'local_atlas_export.exe'
r = dict(result='running', stage=a.stage, sources={}, inputs={}, commands=[], banks=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def run(binary, args, expected=0):
    argv = list(map(str, [binary]+args))
    done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=180)
    log = a.out/('command%02d.log' % len(r['commands']))
    log.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=argv, exit_code=done.returncode, binary_sha256=sha(binary),
                             log=log.name, log_sha256=sha(log)))
    save(a.out/'report.json', r)
    assert done.returncode == expected, log
    return done


try:
    for n in ['tools/run_F3_local_atlas_v1.py', 'tools/local_atlas_v1/inputs.py',
              'tools/local_atlas_v1/oracle.py', 'tools/sustain_osc_v1/oracle.py',
              'tools/idle_texture_v1/profile.py', 'research/F3_local_atlas_v1_plan.json']:
        dest = a.out/'exact_sources'/n
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/n, dest)
        r['sources'][n] = sha(repo/n)
    plan = load(repo/'research/F3_local_atlas_v1_plan.json')
    assert load(consume(a.build/'report.json'))['result'] == 'passed'
    assert run(probe, ['--describe']).stdout.strip() == b'vsl.local-atlas-export/1'
    if a.stage == 'known':
        folder = a.build/'known'
        source, schedule = folder/'known.manifest', folder/'known.trace'
        prefix = a.out/'analytic'
        run(probe, [source, schedule, prefix, 23117, 37])
        wave, rate = sf.read(prefix.with_suffix('.wav'), always_2d=True)
        events = np.loadtxt(schedule, skiprows=1)
        roots, phases, _ = clock(events, len(wave))
        expected = np.zeros_like(wave)
        for order, amp in ((3, .12), (5, .08), (7, .04), (12, .02)):
            gain = 1+.05*(roots-60)
            expected[:, 0] += amp*gain*np.cos(order*phases+.13*order)
            expected[:, 1] += .7*amp*gain*np.cos(order*phases+.13*order+.4)
        error = float(abs(wave-expected).max())
        assert rate == 48000 and wave.shape == (576000, 2) and error < 3e-7
        models = [model_load(folder/('known%d.model' % j))[0] for j in range(3)]
        r['known_alignment'] = alignment(models, load(prefix.with_suffix('.json'))['offsets'])
        r['full_analytic_error_FS'] = error
        # All predeclared bad-input checks must fail before creating audio.
        invalid = []
        for name, text in [
            ('unsigned_overflow', 'VSL_LOCAL_ATLAS_TRACE 1 48000 2\n4294967296 60 1 1\n240 64 1 1\n'),
            ('negative_frame', 'VSL_LOCAL_ATLAS_TRACE 1 48000 2\n-0 60 1 1\n240 64 1 1\n'),
            ('nan', 'VSL_LOCAL_ATLAS_TRACE 1 48000 2\n0 nan 1 1\n240 64 1 1\n'),
            ('past_end', 'VSL_LOCAL_ATLAS_TRACE 1 48000 2\n0 60 1 1\n48000 64 1 1\n'),
            ('tail', schedule.read_text(encoding='utf-8')+'UNEXPECTED\n')]:
            dest = a.out/(name+'.trace')
            dest.write_text(text, encoding='utf-8')
            target = a.out/name
            run(probe, [source, dest, target, 23117, 37], 2)
            assert not target.with_suffix('.wav').exists()
            invalid.append(name)
        for seed, block in [(0, 37), (23117, 513)]:
            target = a.out/('bad_%d_%d' % (seed, block))
            run(probe, [source, schedule, target, seed, block], 1)
            assert not target.with_suffix('.wav').exists()
            invalid.append('seed_or_block_%d_%d' % (seed, block))
        before = sha(prefix.with_suffix('.wav'))
        run(probe, [source, schedule, prefix, 23117, 37], 3)
        assert sha(prefix.with_suffix('.wav')) == before
        r.update(result='known_analytic_alignment_rejections_and_overwrite_passed',
                 invalid_before_output=invalid, overwrite_preserved=True, new_source_read=False)
    else:
        assert a.known and load(consume(a.known/'report.json'))['result'] == 'known_analytic_alignment_rejections_and_overwrite_passed'
        for bank in plan['banks']:
            folder = a.out/bank['name']
            folder.mkdir()
            models, base, paths = [], [], []
            for frozen, phase, name in bank['cases']:
                archive = a.workspace/'baselines'/frozen
                path = archive/'evidence'/phase/name/'voice.model'
                record = load(consume(archive/'manifest.json'))
                entry = next(v for v in record['files'] if v['path'] == path.relative_to(archive).as_posix())
                assert sha(consume(path)) == entry['sha256']
                model, root = model_load(path)
                assert model['basis'].shape == (288, 12, 4)
                models.append(model);base.append(root);paths.append(path)
            assert base[0] < base[1] < base[2]
            manifest(folder/'triplet.manifest', paths, plan['alignment_orders'])
            manifest(folder/'mid.manifest', paths[1:2], 0)
            trace(folder/'trajectory.trace', base[0], base[-1], plan)
            run(build/'local_atlas_driver_checks.exe', [folder/'triplet.manifest'])
            renders = []
            for variant in ('triplet', 'mid'):
                for seed in plan['seeds']:
                    prefix = folder/('%s_%d' % (variant, seed))
                    run(probe, [folder/(variant+'.manifest'), folder/'trajectory.trace', prefix, seed, 512])
                    wave, rate = sf.read(prefix.with_suffix('.wav'), always_2d=True)
                    assert wave.shape == (576000, 2) and rate == 48000 and np.isfinite(wave).all()
                    assert float(abs(wave).max())*.5 < .95
                    renders.append(dict(variant=variant, seed=seed, file=prefix.with_suffix('.wav').name,
                                        sha256=sha(prefix.with_suffix('.wav')), peak_FS=float(abs(wave).max())))
            prefix = folder/'triplet_1_block37'
            run(probe, [folder/'triplet.manifest', folder/'trajectory.trace', prefix, 1, 37])
            for suffix in ('.wav', '.csv'):
                assert sha(prefix.with_suffix(suffix)) == sha((folder/'triplet_1').with_suffix(suffix))
            r['banks'].append(dict(name=bank['name'], models=list(map(str, paths)), root_hz=base,
                                   renders=renders, block_37_512_audio_and_trace_exact=True))
            save(a.out/'report.json', r)
            print('PASS', bank['name'], base, flush=True)
        r.update(result='two_separate_frozen_triplets_rendered', no_refit=True,
                 C_audio_files=12, seconds_per_file=12, repeated_block_files=2,
                 driver_2_12_real_banks_checked=2, shared_DSP_changed=False, hearing=False,
                 physical_RPM_or_load=False, old_failures_reclassified=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(r['result'], flush=True)
