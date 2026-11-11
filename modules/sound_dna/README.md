# sound DNA C11 module · V1

This module generates the procedural DNA voice. It does not contain a vehicle,
cylinder/firing geometry, PAD, noise, room, speaker layout or audio-device backend.
Recording-derived profiles still contain their original mixed acoustic transfer;
the module boundary is not evidence of physical source separation.

| File | Responsibility |
|---|---|
| `profile.*` | Versioned, transactional profile loading, independent base Hz and numeric/frequency limits |
| `texture.*` | Correlated stochastic coefficient statistics and persistent RNG state |
| `oscillator.*` | Harmonic OSC sum with fixed mean phase and time-varying magnitudes |
| `voice.*` | Public lifecycle, pitch/texture/gain control,18ms following and generation clock |

The caller owns a persistent `SdProfile` and one `SdVoice` per independent voice:

```c
/* Loading and initialization happen outside the real-time render callback. */
sd_profile_load(utf8_path, &profile);
sd_voice_init(&voice, &profile, 48271, 1.0, 1.0, 1.0);

/* At a control boundary, then in the render callback: */
sd_voice_set(&voice, relative_pitch, texture_amount, gain);
sd_voice_process(&voice, interleaved_double_stereo, frames);
```

Check the initialization/control return values. Keep the profile alive and
immutable while its voices are running. `sd_voice_process` writes exactly the
requested frame count indefinitely. It performs no allocation, file I/O or source
PCM playback. RNG, oscillator phase and coefficient update state belong to each
voice. Identical profiles, seed, controls and binary give block-size-independent
output. Bit identity across compiler/math-library versions is not promised.

Current output is48kHz, relative pitch0.90–1.10, texture0–1 and gain0–1. Texture
changes magnitude variation while each coefficient's phase remains anchored to
its complex mean. An undefined mean uses zero phase. Temporal microphone phase
variation is intentionally removed in this policy; it is not an acoustic bank or
spatial source model. Fixed coefficient phases do not retime the carrier or engine.

`VSL_SOUND_DNA 1` text profiles store sample rate, analysis cycle1024, hop256,
harmonic/component counts and independent `base_hz`, followed by complex means,
shared directions, AR correlations and per-harmonic residual covariance roots.
The1024-sample cycle is an analysis coordinate, not a hardcoded V10 firing order.
There is no PCM or recording timeline in the profile. Roots and covariance refer
to latent Cartesian coefficient changes, whose magnitudes feed the fixed-phase
oscillators; this is not the old complex-PM rendering policy.

The loader imports `VSL_SUSTAIN_OSC 1` statistics with a default base of rate/window,
preserving the existing V10 data. New profiles have their own base Hz. The loader
rejects profiles whose highest harmonic at1.10× exceeds0.45 of the sample rate.
Numeric, count, version, truncation and trailing-data checks are transactional.
Windows paths use UTF-8 at this API boundary. File loading has a platform-specific
Windows path adapter; synthesis code is portable C11.

Offline compiler: `tools/compile_sound_dna.py input.wav --out NEW_DIRECTORY
--root-hz 110 --name MY_DNA --harmonics 96`. Input root is explicit. It is an
acoustic pitch anchor, not inferred RPM/cylinders. The compiler preserves original
base Hz for playback after normalization. Mono duplication is recorded; stereo
observations stay separate. No implicit filtering, gain matching or compression.

This compiler currently targets stable monophonic/quasiperiodic notes. A moving
engine passage needs a separately justified pitch path, as the original V10
experiment did. Arbitrary polyphony, detuned/inharmonic spectra, space/noise
separation, broad RPM sweeps and control-conditioned profiles remain open work.
One statistical snapshot does not supply all engine states.

`voices/dna_bank_v1` contains one approved V10 context and two analytic additive
fixtures at different roots and model sizes. The fixtures demonstrate reusable
compilation/rendering; they are not two additional real-car validations. Existing
legacy `.dna` files and the frozen driving DSP0.20.0 remain separate interfaces.
