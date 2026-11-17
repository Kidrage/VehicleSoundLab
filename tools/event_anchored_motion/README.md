# Anchored acoustic motion

`track.py` follows only a mutually unique contiguous component from an explicit
time/frequency anchor. Missing or ambiguous observations stop that direction.
There is no new anchor, gap interpolation, harmonic relabel or inferred RPM.
Unresolved doublets and narrow stochastic resonances can still follow a peak;
geometric continuity does not establish physical oscillator identity.

`motion.py` is a source-free sparse frequency-control primitive. Two through
nine time/frequency knots define a continuous-phase oscillator. Pitch and event
duration are independent controls; exact integration preserves phase at knots
and arbitrary host block boundaries. This is offline Python, not a C promotion.

Profiles made from observed points are diagnostic trajectories only. A local
projection using them does not qualify an autonomous event voice or show that
the complete startup/afterfire system is ready. Preserve signed spectral cross
terms and avoid double-counting the continuous engine in the later reference.
