"""Known-tone/noise controls and energy budgets for state observations."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--observed', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from state_dna_v1.window_budget import measure
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True, exist_ok=False)
cycle = np.arange(1024)/1024
known = np.column_stack([.1*np.cos(2*np.pi*5*cycle)+.04*np.cos(2*np.pi*15*cycle+.2),
                         .08*np.cos(2*np.pi*5*cycle+.4)+.02*np.cos(2*np.pi*15*cycle-.3)])
tone = measure(np.tile(known,(512,1)))
noise = measure(np.random.default_rng(261111).normal(0,.02,(512*1024,2)))
assert max(abs(np.array(tone['projected_fraction_LR'])-1)) < 1e-12
assert abs(noise['theoretical_white_noise_fraction']-.375) < 1e-12
assert max(abs(np.array(noise['projected_fraction_LR'])-.375)) < .01
real = {}
for name in ('fall1','rise2','fall2'):
    path = args.observed/name/'normalized_float.wav'
    audio, rate = sf.read(path, always_2d=True)
    assert rate == 48000 and np.isfinite(audio).all()
    real[name] = dict(source_sha256=sha(path), **measure(audio))
report = dict(schema='vsl.dna-analysis-energy-budget/1', result='pass',
    known_tone=tone, known_white_noise=noise, observations=real,
    finding='Four-cycle Hann central harmonic bins retain only3/8 of ideal broadband noise power in their full harmonic cells, while retaining coherent grid OSC power.',
    not_a_fix='Do not multiply the full DNA bysqrt(8/3): that also raises already-correct coherent harmonics. Model omitted inter-harmonic energy separately.',
    source_sha256={p.relative_to(Path(__file__).resolve().parents[1]).as_posix():sha(p) for p in
        [Path(__file__),Path(__file__).parent/'state_dna_v1/window_budget.py']})
(args.out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(dict(result='pass',tone_fraction=tone['projected_fraction_LR'],noise_fraction=noise['projected_fraction_LR'],
    noise_expected_db=float(10*np.log10(.375)),real_3_8k_db={n:r['bands'][4]['projected_minus_cell_db_LR'] for n,r in real.items()})))
