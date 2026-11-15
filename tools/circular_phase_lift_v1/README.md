# Circular phase lift research

Known-input preparation and frozen-path evaluation of a temporal-model
hypothesis. No runtime adoption. See `research/相位半角与连续提升控制V1.md`
and `research/冻结声纹连续相位对照V1.md`.

- `lift.py`: stateful integer-winding lift, with explicit half-turn ambiguity.
- `fixtures.py`: eight analytic controls, including a fast-motion counterexample.
- `replay.py`: paired original-state replay and the one predefined lift rule.
- `audit_oracle.py`: separate interpolation/CDF/unwrap/STFT audit formulas.
- `metrics.py`: all raw/lift/source comparisons and signed power changes.
- The run and independent audit entry points are in the parent `tools` folder.

Holding common phase while lifting relative phase changes L/R waveforms even
though instantaneous powers and relative phasors stay the same. It is not an
equivalent bug fix, physical phase recovery, spatial renderer or driving clock.

The known controls are archived with `carrier_transfer_v1`. Frozen paths are
evaluated separately in `circular_phase_lift_real_v1`; numerical checks do not
establish timbre, native audio, driving-state coverage or spatial qualification.
