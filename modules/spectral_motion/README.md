# Correlated spectral detail

`spectral_motion` composes existing source/filter and amplitude kernels; it
does not contain a vehicle clock, an engine state machine, media playback,
source extraction or spatial processing.

```text
Fresh excitation → spectral_texture FIR bank → per-band contributions
                                                       ↓
MtProfile factors → modal_texture envelope → map → positive gain → stereo
```

`SpmProfile.map[b]` is zero for a static band or a one-based amplitude row.
Several bands may share a row. `MtProfile` is the existing numeric covariance
factor/AR representation; here its rows mean amplitude groups, not oscillator
orders. It contains no original amplitude trajectory. Every row must be used.

Create/destroy on the non-audio thread. The spectral bank, channel ratios and
map are copied; the immutable motion profile is borrowed for the entire voice
lifetime. `spm_voice_tick` and `spm_voice_set` allocate nothing and do no IO.
Amount has the existing finite18ms ramp. All source and modulation states keep
advancing at zero; exact zero uses the original spectral summation arithmetic.
Control gains apply after the internal FIR excitation prefetch, at the actual
output sample. Both channels of one band share a gain. No stereo widening or
room model is introduced.

The F2 host lives in `experiments/idle_microtexture_v1`; it maps its last four
bands to four amplitude rows. Other sources can supply different validated
profiles/maps. This engineering generality does not establish that recordings
of other engines have been extracted or perceptually qualified.
