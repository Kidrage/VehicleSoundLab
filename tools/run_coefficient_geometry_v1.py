"""Known AM/PM through original compiler/C, then six frozen F3 coefficient populations."""
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
    for name in ('known', 'known-audit'):
        p.add_argument('--'+name, type=Path)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from coefficient_geometry_v1.fixtures import rows, counterfactuals
    from coefficient_geometry_v1.moments import observe, summarize, model_covariance
    from sound_dna.statistics import factorize
    from sound_dna.profile import export
    from sound_dna.windowed import coefficients
    from idle_texture_v1.profile import load as model_load
    from exterior_clock_v1.warp import render_positions
    from local_atlas_v1.inputs import manifest
    from joint_motion_controls_v1.observe import observe as observe_wave, summary as wave_summary
    a.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', stage=a.stage, cases=[], sources={}, inputs={}, commands=[])
    def consume(path):
        report['inputs'][str(path)] = sha(path)
        return path
    def run(binary, args):
        argv = list(map(str, [binary]+args))
        done = subprocess.run(argv, capture_output=True, cwd=repo, timeout=180)
        log = a.out/f'command{len(report["commands"]):02d}.log'
        log.write_bytes(done.stdout+done.stderr)
        report['commands'].append(dict(argv=argv, exit_code=done.returncode, log=log.name, sha256=sha(log)))
        save(a.out/'report.json', report)
        assert done.returncode == 0, log
    def snapshot(folder, values, model, root):
        d = observe(values, root, plan['bands_hz'], model)
        arrays = dict(rows=values, **{'model_'+n:v for n,v in model.items()})
        for name, r in d.items():
            arrays.update({name+'_'+k:v for k,v in r.items()})
        np.savez_compressed(folder/'moments.npz', **arrays)
        return dict(root_hz=root, rows=len(values), arrays_sha256=sha(folder/'moments.npz'), moments=summarize(d))
    try:
        sources = ['tools/run_coefficient_geometry_v1.py', 'research/coefficient_geometry_v1_plan.json',
                   'tools/coefficient_geometry_v1/fixtures.py', 'tools/coefficient_geometry_v1/moments.py',
                   'tools/sound_dna/statistics.py','tools/sound_dna/profile.py','tools/sound_dna/windowed.py',
                   'tools/idle_texture_v1/profile.py','tools/exterior_clock_v1/warp.py','tools/local_atlas_v1/inputs.py',
                   'tools/joint_motion_controls_v1/observe.py','tools/native_regions_v1/spectrum.py',
                   'tools/joint_envelopes_v1/features.py']
        for name in sources:
            dest = a.out/'exact_sources'/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, dest)
            report['sources'][name] = sha(dest)
        plan = load(repo/'research/coefficient_geometry_v1_plan.json')
        parent = a.workspace/'baselines/joint_motion_controls_v1'
        for name in ('C_files_sha256.json','voice_files_sha256.json','F2_files_sha256.json'):
            assert all(sha(repo/n) == h for n,h in load(consume(parent/'evidence'/name)).items())
        if a.stage == 'known':
            cfg = plan['known']
            old = a.workspace/'baselines/F3_local_atlas_v1'
            entries = {r['path']:r['sha256'] for r in load(consume(old/'manifest.json'))['files']}
            def frozen(name):
                path = consume(old/name)
                assert sha(path) == entries[name]
                return path
            binary = a.out/'local_atlas_export.exe'
            shutil.copy2(frozen('evidence/bin/local_atlas_export.exe'), binary)
            assert sha(binary) == '90ce22a9169689121f3d2c41b49ae8994dfcb6f1f043f85c395efa4912990d6f'
            known = a.out/'C_known'
            known.mkdir()
            models = []
            for j in range(3):
                path = known/f'known{j}.model'
                shutil.copy2(frozen(f'evidence/build2/known/known{j}.model'), path)
                models.append(path)
            manifest(known/'known.manifest', models)
            shutil.copy2(frozen('evidence/build2/known/known.trace'), known/'known.trace')
            run(binary, [known/'known.manifest',known/'known.trace',known/'replay',23117,512])
            assert sha(known/'replay.wav') == sha(frozen('evidence/known1/analytic.wav'))
            report.update(C_known_576000frame_WAV_exact=True, binary_sha256=sha(binary))
            native = load(consume(a.workspace/'baselines/F3_joint_envelopes_v1/source/research/F3_joint_envelopes_v1_plan.json'))
            for name in cfg['cases']:
                folder = a.out/name
                folder.mkdir()
                values = rows(cfg, name)
                model, stats = factorize(values,cfg['harmonics'],cfg['components_cap'])
                export(folder/'voice.model',model,cfg['root_hz'])
                manifest(folder/'bank.manifest', [folder/'voice.model'])
                (folder/'bank.trace').write_text(f'VSL_LOCAL_ATLAS_TRACE 1 {cfg["C_frames"]} 1\n0 {cfg["root_hz"]} 1 1\n',encoding='ascii')
                row = dict(label=name, compiler_statistics=stats, model_sha256=sha(folder/'voice.model'),
                           **snapshot(folder,values,model,cfg['root_hz']), renders=[])
                for seed in cfg['seeds']:
                    prefix = folder/f'C_seed{seed}'
                    run(binary,[folder/'bank.manifest',folder/'bank.trace',prefix,seed,cfg['C_block']])
                    audio,rate = sf.read(prefix.with_suffix('.wav'),always_2d=True)
                    assert rate == 48000 and audio.shape == (cfg['C_frames'],2) and np.isfinite(audio).all()
                    d = observe_wave(audio[cfg['C_analysis_first']:],native)
                    np.savez_compressed(folder/f'wave_seed{seed}.npz',**d)
                    result = dict(seed=seed,C_files_sha256={s:sha(prefix.with_suffix(s)) for s in ('.wav','.json','.csv')},
                                  wave_arrays_sha256=sha(folder/f'wave_seed{seed}.npz'),**wave_summary(d,1e-10))
                    std = np.array(result['HF_std_dB'])
                    if name == 'PM_only':
                        assert std.min() > plan['gates']['known_PM_C_each_HF_band_std_min_dB']
                    if name == 'steady':
                        assert std.max() < plan['gates']['known_steady_C_each_HF_band_std_max_dB']
                    row['renders'].append(result)
                if name == cfg['block_identity_case']:
                    run(binary,[folder/'bank.manifest',folder/'bank.trace',folder/'C_block37',cfg['seeds'][0],cfg['identity_block']])
                    assert sha(folder/'C_block37.wav') == row['renders'][0]['C_files_sha256']['.wav']
                    row['block37_512_WAV_exact'] = True
                report['cases'].append(row)
                save(a.out/'report.json',report)
                print('PASS original compiler/C coefficient control',name,flush=True)
            report['result'] = 'known_AM_PM_geometry_observed'
        else:
            assert a.known and a.known_audit
            known, audit = [load(consume(d/'report.json')) for d in (a.known,a.known_audit)]
            assert known['result'] == 'known_AM_PM_geometry_observed' and audit['result'] == 'independent_coefficient_geometry_audit_passed'
            assert audit['producer_report_sha256'] == sha(a.known/'report.json')
            bank_plan = load(consume(repo/plan['real']['bank_plan']))
            for bank in bank_plan['banks']:
                for archive, attempt, label in bank['cases']:
                    folder = a.out/label
                    folder.mkdir()
                    old = a.workspace/'baselines'/archive
                    entries = {r['path']:r['sha256'] for r in load(consume(old/'manifest.json'))['files']}
                    def frozen(name):
                        path = consume(old/name)
                        assert sha(path) == entries[name]
                        return path
                    source = old/'evidence'/attempt/label
                    relative = source.relative_to(old).as_posix()
                    selection = load(frozen(relative+'/selection.json'))
                    result = load(frozen(relative+'/result.json'))
                    native,rate = sf.read(frozen(relative+'/native.wav'),always_2d=True)
                    assert rate == 48000
                    positions = np.load(frozen(relative+'/coordinates.npz'))['source_seconds']
                    normalized,rate = sf.read(frozen(relative+'/normalized.wav'),always_2d=True)
                    cutoff = result['extraction']['phase']['source_cutoff_hz']
                    rebuilt = render_positions(native,selection['case']['seconds'][0],positions,cutoff)
                    assert np.array_equal(rebuilt.astype('float32').astype(float),normalized)
                    values = coefficients(rebuilt,288)
                    model,root = model_load(frozen(relative+'/voice.model'))
                    assert model['basis'].shape == (288,12,4)
                    covariance = model_covariance(model)
                    centered = values-values.mean(axis=0)
                    errors = []
                    for h in range(288):
                        g = slice(h*4,h*4+4)
                        target = centered[:,g].T@centered[:,g]/(len(values)-1)
                        difference = abs(covariance[g,g]-target)
                        assert np.all(difference <= plan['gates']['marginal_covariance_absolute']+plan['gates']['marginal_covariance_relative']*abs(target))
                        errors.append(float(difference.max()))
                    assert abs(model['mean'].ravel()-values.mean(axis=0)).max() < 1e-15
                    np.savez_compressed(folder/'source.npz',native=native,positions=positions,rebuilt=rebuilt,normalized_FLOAT=normalized)
                    row = dict(label=label,archive=archive,attempt=attempt,source_start=selection['case']['seconds'][0],cutoff_hz=cutoff,
                               source_arrays_sha256=sha(folder/'source.npz'),source_DOUBLE_rebuild_FLOAT_exact=True,
                               maximum_original_marginal_covariance_error=float(max(errors)),variants=[])
                    for variant, data in counterfactuals(values).items():
                        dest = folder/variant
                        dest.mkdir()
                        variant_model = model if variant == 'full' else factorize(data,288,12)[0]
                        row['variants'].append(dict(label=variant,**snapshot(dest,data,variant_model,root)))
                    report['cases'].append(row)
                    save(a.out/'report.json',report)
                    print('PASS frozen F3 coefficient geometry',label,flush=True)
            report['result'] = 'six_F3_coefficient_geometries_observed'
        report.update(new_audio_candidate=False,heard=False,runtime_DSP_or_model_changed=False)
    except Exception as exc:
        report.update(result='failed',error=repr(exc))
        raise
    finally:
        save(a.out/'report.json',report)


if __name__ == '__main__':
    main()
