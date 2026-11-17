# Crank rotation

Independent, source-conditioned sustained OSC core for a cranking candidate.
`ck_init` copies the validated profile and prepares stationary states/LUT on a
non-audio thread. `ck_tick` allocates nothing and performs no I/O. A rising
`gate` marks a new action; its caller owns audible permission/attack/release.
The current caller is the optional `ScVoice` rotation branch; the production
vehicle event pool does not yet select this candidate.

96 maximum non-harmonic carriers share a pitch integral and a bounded acoustic
AM driver. Each mode has independent fresh complex stochastic variation and
an authored L/R phase offset. Three amplitude states follow action progress;
carrier and random correlation time scales do not stretch with the action.
Learned AM and spectral line widths are not physical shaft RPM or damping.

`coherence` balances persistent carrier and stochastic sidebands. Mode
`width_hz`, three stereo amplitudes, L/R phase, per-band AM coefficients and
`flutter_hz` are profile controls. `ScVoice` additionally supplies pitch,
strength, core/texture mix and nine coarse envelope controls. The residual
FIR is an excitation colour filter, not a room response. See the result report
and frozen listening artifacts before promoting a new profile.
