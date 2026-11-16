"""Read-only inventory of the existing stereo law, not a fit or causal diagnosis."""
import argparse
import os
from pathlib import Path
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists()
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    repo = Path(__file__).resolve().parents[1]
    root = a.workspace/'references/analysis/relative_phase_v1/real1'
    folder = root/'F3 Fifth First Late'
    inputs = {str(path):sha(path) for path in (root/'report.json', folder/'profile.npz', folder/'training.npz')}
    with np.load(folder/'profile.npz') as f: model = {k:f[k] for k in f.files}
    with np.load(folder/'training.npz') as f: training = {k:f[k] for k in f.files}
    source = load(root/'report.json')
    audio_path = root.parent/'audio1/report.json'
    audio_source = load(audio_path)
    inputs[str(audio_path)] = sha(audio_path)
    code = ('tools/relative_phase_v1/profile.py', 'tools/relative_phase_v1/coordinates.py',
        'tools/relative_phase_v1/render.py', 'tools/radial_copula_v1/latent.py',
        'tools/trace_relative_phase_representation_v1.py')
    # Except this new inventory tool, these are the actual frozen producer sources.
    for name in code[:-1]:
        owner = audio_source if name.endswith('/render.py') else source
        assert sha(repo/name) == owner['sources'][name]
    assert model['fixed_phase'].shape == (288, 2)
    assert model['basis'].shape == (1152, 12)
    assert training['scores'].shape == (40, 1152)
    save(a.out, dict(result='existing_relative_phase_representation_traced_without_training',
        sources={name:sha(repo/name) for name in code}, inputs=inputs,
        model_shapes={k:list(v.shape) for k,v in model.items()},
        training_shapes={k:list(v.shape) for k,v in training.items()},
        observed_rows=40, oscillator_orders=288, feature_dimensions=1152, shared_components=12,
        features='576 L/R amplitudes + 288 common-phase + 288 relative-phase coordinates',
        retained='empirical scalar marginals, 12-component joint rank-Gaussian structure, per-coordinate lag1 AR parameter',
        discarded_by_representation='off-diagonal covariance of the residual feature vector; cross-coordinate lagged coupling; temporal dependencies beyond the imposed scalar AR1 law',
        limitation='This code trace establishes representation limits, not their audible importance or the cause of electronic timbre. 40 overlapping/context-linked rows are not 40 independent recordings.',
        old_source_CV_error_L2=source['CV_error_L2'],
        retained_failed_inventory='E:/VehicleSoundLab/references/analysis/relative_phase_representation_review_20261116_failed1',
        current_new_C1_source_eligible_for_statistics=False,
        no_new_training_generation_fitting_audio_C_preset_or_room_change=True,
        next='Known temporal/cross-coordinate controls, then read-only preservation assessment on the existing saved profile; new C1 source admission remains a separate failed gate.'))
    print('RELATIVE_PHASE_REPRESENTATION_TRACED', 288, 1152, 12, 40, flush=True)


if __name__ == '__main__': main()
