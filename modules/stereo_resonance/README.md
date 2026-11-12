# Two-channel continuous resonance

Optional C11 detail source. `RvsProfile` owns no audio samples; each band stores a
real two-channel VAR predictor, a lower-triangular innovation root, bandpass SOS,
gain and a discrete Lyapunov certificate. Parameters are independent of engine
family. The current fit is ONE A startup-settling cabin observation, not a full
idle/acceleration atlas or an accepted sound.

- `profile.*`: non-real-time validation. Requires positive innovation diagonals,
  stable SOS, positive `P`, and positive `P - FᵀPF` for the companion state `F`.
- `voice.*`: borrowed immutable profile, separate channel histories/innovations,
  continuous recurrence, postfilters and an 18 ms amount follower. Caller must
  retain the profile for the voice lifetime. No allocation, file, UI, PCM or
  independent engine/RPM clock in `rvs_voice_tick`.
- `stereo_resonance_io/profile.*`: separate transactional text loading. Invalid
  input leaves the destination unchanged. Initialization/warmup are non-RT.

`rvs_voice_init(voice, profile, seed, amount)` validates and prewarms;
`rvs_voice_set` sets 0..1 detail amount; `rvs_voice_tick` returns stereo scaled
output and optional unscaled stereo. All histories/RNG continue at amount zero.
The init destination is unspecified on warmup failure; only successful init may
be rendered. Do not edit the borrowed profile while running.

This represents joint recorded-channel statistics. It does not identify cylinder
banks or physically separate a room, intake, exhaust or friction source. It adds
no room processor; the source fit can still contain recording/vehicle transfer.
No cycle envelope has been qualified for this context. Future driving integration
must consume the existing controller, own models in takes, define supported
root/load ranges, and route the observed stereo once through the existing bed.
Do not invent surround/height/LFE data from these two observed channels.

Current host: `experiments/stereo_resonance_v1/probe.c`, offline double output.
The standalone block timing is not an audio-device or full-driver budget test.
The module is not enabled in a native monitor, driver, default or schema6 take.
