"""Build a separate mean residual and bounded temporal model for accepted A."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', required=True, type=Path)
parser.add_argument('--probe', required=True, type=Path)
parser.add_argument('--out', required=True, type=Path)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from residual_osc_v1.fit import fit, export as export_residual
from residual_motion_v1.sources import read
from residual_motion_v1.features import powers
from residual_motion_v1.fit import estimate, export

args.out.mkdir(parents=True, exist_ok=False)
reference, base, provenance = read(args.workspace, repo)
rows, evidence = fit(reference, base[24000:])
export_residual(args.out/'A_moving.residual', rows)
sf.write(args.out/'reference.wav', reference, 48000, subtype='FLOAT')
sf.write(args.out/'accepted_pair.wav', base, 48000, subtype='FLOAT')
_, target_power = powers(reference)
np.savez_compressed(args.out/'reference_power.npz', power=target_power)
blocks, residual_blocks, renders = [], [], []
length = len(reference)
for seed in (8121907, 31091, 95173):
    path = args.out/f'static_{seed}.wav'
    command = [str(args.probe), str(args.out/'A_moving.residual'), str(path), '8', '1', '1', str(seed)]
    subprocess.run(command, check=True, capture_output=True, timeout=90)
    x, rate = sf.read(path, always_2d=True)
    assert rate == 48000 and x.shape == base.shape and np.isfinite(x).all()
    # Nonoverlapping source-length blocks; none is called an independent
    # recorded passage. Separate seeds probe procedural estimator variability.
    for start in range(24000, len(x)-length+1, length):
        _, p = powers((x+base)[start:start+length])
        _, q = powers(x[start:start+length])
        blocks.append(p);residual_blocks.append(q)
    renders.append(dict(seed=seed, command=command, sha256=sha(path)))
    print('static seed', seed, 'blocks', len(blocks), flush=True)
basis, rho, temporal = estimate(target_power, blocks, residual_blocks)
export(args.out/'A_moving.motion', basis, rho)
paths = [Path(__file__), *sorted((repo/'tools/residual_motion_v1').glob('*.py')),
         repo/'tools/residual_osc_v1/fit.py', repo/'tools/residual_osc_v1/spectrum.py',
         repo/'tools/drive_evidence_v1/sources.py']
report = dict(schema='vsl.residual-motion-fit/1', provenance=provenance, static_fit=evidence,
    static_rows=rows, temporal=temporal, rho=rho.tolist(), basis=basis.tolist(),
    observation_frames=len(target_power), procedural_comparison_blocks=len(blocks),
    probe_sha256=sha(args.probe), renders=renders, source_sha256={p.relative_to(repo).as_posix(): sha(p) for p in paths},
    static_model_sha256=sha(args.out/'A_moving.residual'), motion_model_sha256=sha(args.out/'A_moving.motion'),
    limits=['One short mixed moving-tailpipe context; no state or physical noise separation',
            'Positive variance debt uses a first-order mixture sensitivity; negative debt cannot be removed by added AM',
            'Linear trend removed; overlapping observations are correlated',
            'Stationary AR/magnitude hypothesis requires independent C output and listening checks'])
for p in paths:
    target = args.out/'exact_sources'/p.relative_to(repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, target)
(args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(factors=len(rho), rho=rho.tolist(), bound_scale=temporal['common_bound_scale'],
                      negative_mass=temporal['negative_eigenvalue_mass'], residual_fractions=temporal['residual_power_fraction']), ensure_ascii=False))
