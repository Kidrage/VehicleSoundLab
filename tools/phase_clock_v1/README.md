# Offline phase-clock candidates

These candidates refine an observed acoustic coordinate. They do not identify
physical RPM, throttle, torque or injector state. None has passed the combined
original-fixture, independent-fixture and real-recording qualification.

| File | Responsibility |
|---|---|
| `chirplet.py` | Centered8kHz resampling,80ms Hann/5ms hop; observed power across explicit−2000..2000Hz/s chirp slopes. The maximum across slopes is a peak-observation score, not a calibrated PSD. |
| `tracking.py` | Use a complete ordinary FFT path first; try a complete chirplet path only after whole-path failure. Never fill missing reference observations or splice partial paths. |
| `projection.py` | Two-cycle reference phase,−30dB support gate, common L/R inverse coordinate and separate-carrier diagnostics. A joint least-squares prototype was simplified after proving equality to this Hann projection. |
| `debiased.py` | Four-cycle phase with first-order Hann second-moment inverse;9-point cubic phase-curvature estimate. Preserves longer frequency selectivity, but fails the original hardest fixture. |
| `fixtures.py` | Explicit coherent stereo oscillator sweeps, known colour, noise and missing/contaminated-reference controls. No recording models. |

`tools/state_dna_v1/compare.describe` accepts an explicit `phase_refiner` callback;
its original default remains. The global separate-carrier gate is conservative:
pitch-dependent transfer phase can fail it even with a coherent engine. Passing
that gate is also not proof of physical source separation or natural timbre.

Reproduce with `verify_phase_clock_v1.py --workspace DATA --method debiased
--tracker hybrid --out NEW_DIRECTORY`. That command passes16independent fixtures;
also run `explore_phase_clock_v1.py --method debiased` against the original
repeats, where the hardest known sweep still has1.007dB error. A single green
command does not authorize promoting a model. See the combined [research note](../../research/离线时钟校验V1.md).
