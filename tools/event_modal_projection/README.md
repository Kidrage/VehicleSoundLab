# Normalized event OSC projection

Offline acoustic representation diagnostics. `basis.py` keeps the existing twelve
frequencies and nominal phases/sweep but ignores old amplitudes, including zeros.
`project.py` uses normalized pivoted QR to measure fixed/quadrature sparse-envelope
capacity; `measure.py` reuses the native signed spectral power bookkeeping.

The source is fitted in observed L/R independently. These are recording channels,
not spatial objects or identified engine parts. No stereo fold, room model,
background waveform subtraction, random generator or runtime voice is added.

Full-source least-squares is an upper-capacity description. The withheld ten-ms
blocks test interpolation in the same event only. Source-derived coefficients
may describe one trajectory; neither result establishes reusable autonomous
generation, measured RPM, timbre acceptance or an isolated mechanical residual.
Keep projection/remainder/cross power together. A local projection/raw ratio is
not a physical coherent fraction and can exceed one through negative cross terms.

Run `verify_event_modal_projection_v1.py` before `inspect_event_modal_projection_v1.py`;
then `audit_event_modal_projection_v1.py` independently reads the saved source,
coefficients and DOUBLE WAVs without importing these projection/budget modules.
