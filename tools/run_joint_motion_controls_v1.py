"""Known motion/AM controls first; then frozen C source texture ablations."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--stage', choices=['known', 'real'], required=True)
    p.add_argument('--known', type=Path)
    p.add_argument('--known-audit', type=Path)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from joint_motion_controls_v1.fixtures import cases, render
    from joint_motion_controls_v1.observe import observe, summary
    from local_atlas_v1.inputs import manifest
    a.out.mkdir(parents=True, exist_ok=False)
    r = dict(result='running', stage=a.stage, cases=[], commands=[], sources={}, inputs={})
    def consume(path):
        r['inputs'][str(path)] = sha(path)
        return path
    def run(binary, argv):
        argv = list(map(str, [binary]+argv))
        done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=180)
        log = a.out/f'command{len(r["commands"]):02d}.log'
        log.write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(argv=argv, exit_code=done.returncode, log=log.name, sha256=sha(log)))
        save(a.out/'report.json', r)
        assert done.returncode == 0, log
        return done
    try:
        names = ['tools/run_joint_motion_controls_v1.py','research/joint_motion_controls_v1_plan.json',
                 'tools/joint_motion_controls_v1/fixtures.py','tools/joint_motion_controls_v1/observe.py',
                 'tools/native_regions_v1/spectrum.py','tools/joint_envelopes_v1/features.py',
                 'tools/local_atlas_v1/inputs.py','tools/sound_dna/profile.py']
        for name in names:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            r['sources'][name] = sha(dest)
        plan = load(repo/'research/joint_motion_controls_v1_plan.json')
        parent = a.workspace/'baselines/F3_driver_joint_v1'
        for name in ['C_files_sha256.json','voice_files_sha256.json','F2_files_sha256.json']:
            protected = load(consume(parent/'evidence'/name))
            assert all(sha(repo/n) == h for n, h in protected.items())
        native = load(consume(a.workspace/'baselines/F3_joint_envelopes_v1/source/research/F3_joint_envelopes_v1_plan.json'))
        floor = plan['gates']['PC1_covariance_trace_floor_dB2']
        if a.stage == 'known':
            old = a.workspace/'baselines/F3_local_atlas_v1'
            old_manifest = load(consume(old/'manifest.json'))
            entries = {row['path']:row['sha256'] for row in old_manifest['files']}
            def frozen(name):
                path = consume(old/name)
                assert sha(path) == entries[name]
                return path
            binary = a.out/'local_atlas_export.exe'
            shutil.copy2(frozen('evidence/bin/local_atlas_export.exe'), binary)
            known = a.out/'C_known'
            known.mkdir()
            paths = []
            for j in range(3):
                path = known/f'known{j}.model'
                shutil.copy2(frozen(f'evidence/build2/known/known{j}.model'), path)
                paths.append(path)
            manifest(known/'known.manifest', paths)
            shutil.copy2(frozen('evidence/build2/known/known.trace'), known/'known.trace')
            assert run(binary, ['--describe']).stdout.strip() == b'vsl.local-atlas-export/1'
            run(binary, [known/'known.manifest',known/'known.trace',known/'replay',23117,512])
            assert sha(known/'replay.wav') == sha(frozen('evidence/known1/analytic.wav'))
            r['C_known_576000frame_WAV_exact'] = True
            r['binary_sha256'] = sha(binary)
            for row in cases(plan):
                audio = render(plan, row['family'], row['motion'], row['modulation'])
                d = observe(audio, native)
                folder = a.out/row['label']
                folder.mkdir()
                np.savez_compressed(folder/'arrays.npz', **d)
                r['cases'].append(dict(row, arrays_sha256=sha(folder/'arrays.npz'),
                                       windows=len(d['window_starts']), **summary(d, floor)))
                save(a.out/'report.json', r)
                print('PASS known motion/AM', row['label'], flush=True)
            r['result'] = 'known_motion_and_AM_observed'
        else:
            assert a.known and a.known_audit
            known, audit = load(consume(a.known/'report.json')), load(consume(a.known_audit/'report.json'))
            assert known['result'] == 'known_motion_and_AM_observed' and known['C_known_576000frame_WAV_exact']
            assert audit['result'] == 'independent_motion_observation_audit_passed'
            assert audit['producer_report_sha256'] == sha(a.known/'report.json')
            binary = consume(a.known/'local_atlas_export.exe')
            assert sha(binary) == known['binary_sha256']
            index = load(consume(repo/'voices/F3_fifth_local_v1/index.json'))
            cfg = plan['real']
            for group in cfg['groups']:
                bank = a.out/group
                bank.mkdir()
                rows = [row for row in index['profiles'] if row['group'] == group]
                assert [row['point'] for row in rows] == ['early','mid','late']
                paths = []
                roots = [row['root_hz'] for row in rows]
                for row in rows:
                    source = consume(repo/row['path'])
                    assert sha(source) == row['sha256']
                    target = bank/Path(row['path']).name
                    shutil.copy2(source, target)
                    paths.append(target)
                manifest(bank/'bank.manifest', paths)
                for trajectory in cfg['trajectories']:
                    frames = np.arange(0,cfg['frames'],cfg['event_hop'])
                    if trajectory == 'static_mid':
                        targets = np.full(len(frames),roots[1])
                    else:
                        u = np.maximum(0,frames-cfg['analysis_first'])/(cfg['frames']-cfg['analysis_first']-cfg['event_hop'])
                        targets = roots[0]+(roots[-1]-roots[0])*u
                    for detail in cfg['detail_ablation']:
                        seeds = cfg['detail1_seeds'] if detail else [cfg['detail0_seed']]
                        trace = bank/f'{trajectory}_detail{detail}.trace'
                        trace.write_text(f'VSL_LOCAL_ATLAS_TRACE 1 {cfg["frames"]} {len(frames)}\n'+
                            ''.join(f'{f} {hz:.17g} {detail} {cfg["gain"]}\n' for f,hz in zip(frames,targets)),encoding='utf-8')
                        for seed in seeds:
                            label = f'{group}_{trajectory}_detail{detail}_seed{seed}'
                            folder = a.out/label
                            folder.mkdir()
                            prefix = folder/'C_source'
                            run(binary, [bank/'bank.manifest',trace,prefix,seed,512])
                            audio, rate = sf.read(prefix.with_suffix('.wav'),dtype='float64',always_2d=True)
                            assert rate == 48000 and audio.shape == (cfg['frames'],2) and np.isfinite(audio).all()
                            d = observe(audio[cfg['analysis_first']:],native)
                            np.savez_compressed(folder/'arrays.npz',**d)
                            r['cases'].append(dict(label=label,group=group,trajectory=trajectory,detail=detail,seed=seed,
                                models=[p.relative_to(a.out).as_posix() for p in paths],trace=trace.relative_to(a.out).as_posix(),
                                C_files_sha256={suffix:sha(prefix.with_suffix(suffix)) for suffix in ['.wav','.csv','.json']},
                                arrays_sha256=sha(folder/'arrays.npz'),windows=len(d['window_starts']),**summary(d,floor)))
                            save(a.out/'report.json',r)
                            print('PASS C source ablation',label,flush=True)
            r.update(result='frozen_C_source_motion_texture_ablations_observed',binary_sha256=sha(binary),
                     C_files_changed=False,source_only_not_full_driver=True,audio_candidate=False,heard=False)
    except Exception as exc:
        r.update(result='failed', error=repr(exc))
        raise
    finally:
        save(a.out/'report.json',r)


if __name__ == '__main__':
    main()
