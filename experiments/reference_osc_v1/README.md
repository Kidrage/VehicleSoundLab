# Reference-derived OSC diagnostic V1

Portable C11 amplitude/cubic-phase oscillator renderer. The text model stores
parameter trajectories from an approved recording excerpt, not PCM, wavetables
or an event-trigger source. It is not yet an RPM/load-conditioned engine voice.

- `model.h/.c`: bounded, transactional coefficient loader; allocation outside render.
- `oscillator.h/.c`: block-independent stereo AM/FM synthesis and smoothed high mix.
- `probe.c`: standalone file renderer; this Windows harness links frozen V020 WAV I/O.
- `checks.c`: analytic control, block invariance, smoothing and malformed-model handling.

`RoModel` must be zero-initialized before its first load; successful load replaces
owned data, failed load preserves it. The player borrows the model for its entire
lifetime. Loading/freeing a borrowed model during processing is unsupported.

Model rows contain group0 base or group1 high, with six coefficients for each
recording channel: A0 A1 phase0 omega0 c2 c3. Segment time is in seconds from
its start; amplitude interpolates over segment frames. L/R are observations,
not physical engine banks. Uncovered frames render silence. Analysis windows
leave edge regions unsupported; this is not a steady-state voice generator.

Build/test commands and scope: `research/素材驱动OSC回查V1.md`.
The source and output hashes are recorded with the local analysis evidence.
