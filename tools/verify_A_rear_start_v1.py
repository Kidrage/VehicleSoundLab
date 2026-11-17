"""Check fixed exterior startup crops with actual C and editable parameter projects."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_authoring.model import synth
from event_authoring.native import Renderer
from event_authoring.temporal_fit import band_curves
from event_designer.workspace import EventWorkspace
from research_archive_v1 import load, save, sha


EDGES = ((0,60), (60,300), (300,1200), (1200,4500), (4500,14000), (14000,24001))


def psd(x):
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    n = 2048
    window = .5-.5*np.cos(2*np.pi*np.arange(n)/n)
    rows = []
    for start in range(0, len(x)-n+1, n//2):
        z = np.fft.rfft(x[start:start+n]*window[:,None], axis=0)
        power = (z.real*z.real+z.imag*z.imag)/(48000*float(window@window))
        power[1:-1] *= 2
        rows.append(power.mean(axis=1))
    return np.fft.rfftfreq(n, 1/48000), np.mean(rows, axis=0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--kind', choices=('crank', 'catch'), action='append')
    p.add_argument('--catch-profile', type=Path)
    args = p.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_verification.py')
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1')
    preparation = load(root/'selection1/report.json')
    selection = load(root/'selection1/selection.json')
    renderer = Renderer(repo)
    workspace = EventWorkspace(repo, Path('E:/VehicleSoundLab/designs/events'))
    report = dict(result='running', goal_complete=False, physical_source_separated=False,
                  physical_RPM_identified=False, timbre_accepted=False)
    results = {}
    try:
        source = Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
        assert sha(source) == selection['source_sha256']
        for kind, name in [('crank', 'early'), ('catch', 'later')]:
            if args.kind and kind not in args.kind:
                continue
            path = args.catch_profile if kind == 'catch' and args.catch_profile else root/(kind+'1')/'profile.json'
            doc = load(path)
            original_job = load(root/'selection1'/(kind+'.job.json'))
            for key in ('source', 'seconds', 'background_seconds', 'gated', 'analysis_scope'):
                assert doc['source_job'][key] == original_job[key]
            raw, rate = sf.read(root/'selection1'/(name+'-original.wav'), always_2d=True)
            background, _ = sf.read(root/'selection1/background-original.wav', always_2d=True)
            duration = len(raw)/48000
            with sf.SoundFile(source) as stream:
                first, last = preparation['selections'][name]['frames']
                stream.seek(first)
                assert np.array_equal(raw, stream.read(last-first, dtype='float64', always_2d=True))
            folder = out/kind
            folder.mkdir()
            frequency, raw_power = psd(raw)
            _, noise_power = psd(background)
            excess = np.maximum(raw_power-noise_power, 0)
            targets = [float(excess[(frequency>=lo)&(frequency<hi)].sum()*48000/2048) for lo,hi in EDGES]
            reported = doc['fit']['source_response_fit']['bands']
            np.testing.assert_allclose([r['target_power'] for r in reported], targets, rtol=2e-12, atol=1e-15)
            _, raw_curves = band_curves(raw)
            _, noise_curves = band_curves(background)
            temporal = np.maximum(raw_curves-noise_curves.mean(axis=1)[:,None], 0)
            temporal /= np.maximum(temporal.mean(axis=1), 1e-30)[:,None]
            seeds = []
            seed_values=(27431,48271,93931,17389,13007,90419,58211,71237) if kind=='catch' else (27431,48271,93931,17389)
            for seed in seed_values:
                values = dict(seconds=2., seed=seed, hold_seconds=duration)
                actual, native = renderer.render(doc['parameters'], kind, values)
                python = synth(doc['parameters'], seed=seed, seconds=2.,
                               release_at=duration if kind=='crank' else None)
                python = np.pad(python, (0,len(actual)-len(python)))
                error = float(np.max(abs(actual-python)))
                assert error < 3e-7
                f, spectrum = psd(actual[:len(raw)])
                bands = []
                for (lo,hi), target in zip(EDGES, targets):
                    generated = float(spectrum[(f>=lo)&(f<hi)].sum()*48000/2048)
                    db = float(10*np.log10(max(generated,1e-30)/max(target,1e-30)))
                    passed = abs(db)<=3 if target>=sum(targets)*1e-4 else generated<=max(target*2,sum(targets)*2e-4)
                    bands.append(dict(hz=[lo,hi], target_power=target, generated_power=generated,
                                      error_db=db, passed=bool(passed)))
                _, generated_curves = band_curves(actual[:len(raw)])
                generated_curves /= np.maximum(generated_curves.mean(axis=1),1e-30)[:,None]
                errors = np.sqrt(np.mean((temporal-generated_curves)**2,axis=1)).tolist()
                assert not np.any(actual[round((duration+.1)*48000):])
                sf.write(folder/(str(seed)+'.wav'), actual, 48000, subtype='FLOAT')
                seeds.append(dict(seed=seed, C_python_max_error_FS=error, bands=bands,
                    four_band_normalized_shape_rmse=errors, peak=float(np.max(abs(actual))),
                    all_spectral_gates_pass=all(r['passed'] for r in bands), metadata=native))
            results[kind] = dict(seeds=seeds, source_document=str(path))
            failures = [(s['seed'], b['hz'], b['error_db']) for s in seeds for b in s['bands'] if not b['passed']]
            assert not failures, failures
            doc = deepcopy(doc)
            doc['viewpoint'] = 'exterior'
            controls = dict(seconds=2., seed=27431, hold_seconds=duration)
            project = workspace.create(dict(package=dict(schema='vsl.event-design/1', document=doc, controls=controls)))
            project = workspace.render(dict(id=project['id']))
            version = workspace.root/project['id']/project['last_version']
            actual, _ = sf.read(version/'synthesis.wav', dtype='float32')
            expected, _ = sf.read(folder/'27431.wav', dtype='float32')
            assert np.array_equal(actual, expected)
            shutil.copytree(workspace.root/project['id'], folder/'editable-project')
            save(folder/'event-profile.json', doc)
            results[kind] = dict(seeds=seeds, editable_project=project['id'], source_free_C_PCM_exact=True,
                document=str(folder/'event-profile.json'), reliable_groups=doc['fit']['contour_fit']['bands'])
            print(kind, 'four C seeds, original frames and editable project passed', flush=True)
        bindings = load(root/'selection1/runtime.json')
        assert len(bindings)==459 and all(sha(repo/name)==digest for name,digest in bindings.items())
        report.update(result='passed', profiles=results, runtime_voice_files_unchanged=459,
                      author_bridge_sha256=renderer.identity)
    except Exception as error:
        report.update(result='failed', profiles=results, error=repr(error))
        raise
    finally:
        save(out/'report.json', report)


if __name__=='__main__':
    main()
