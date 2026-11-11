# Low rumble · V2

Independent portable C11 low-frequency source. `profile.*` loads/validates the
spectral model; `cloud.*` owns stochastic quadrature coefficients and OSC clocks;
`voice.*` owns control following and output filters. The accepted sound DNA module
is neither modified nor called by this module.

```c
/* Check return values; initialize outside the real-time callback. */
lr_profile_load(utf8_path, &profile);
lr_voice_init(&voice, &profile, 48444, 1.0, 0.6);
lr_voice_set(&voice, relative_pitch, amount);
lr_voice_process(&voice, mono_output, frame_count);
```

Profile storage is borrowed and must remain immutable/alive while the voice runs.
Each voice has independent RNG, clocks, quadrature history and filter state. No
allocation, file access, recording playback or source timeline occurs in process.
Output is one mono source at 48kHz, for a separate mixer/spatial renderer. Equal
L/R monitoring is an explicit listener mapping, not recorded banks or LFE routing.

`VSL_LOW_RUMBLE 2` stores rate, count, uniform grid origin/step, correlation time
and per-carrier amplitudes. Its loader checks count, finite/range/frequency/energy
budgets, truncation and trailing data before committing the complete model. File
paths use UTF-8 with a Windows adapter; the synthesis implementation is C11.

The current bank uses 192 carriers at 30.703125..299.296875Hz. Independent zero-mean
Gaussian quadratures follow a first-order autoregressive process at 250Hz. Smooth
interpolation has pointwise variance compensation. The coefficient correlation
time is bounded to 25..65ms by the offline recipe. No sinusoidal pitch LFO, saw
or square waveform is added. Stochastic quadrature variation makes each spectral
region diffuse; unlike DNA, it intentionally has no stable mean-phase tone.
Amount controls only source gain, with 18ms following. Relative pitch is bounded
to 0.90..1.10; its changes do not retime stochastic updates or elapsed playback.

Second-order Butterworth 24Hz highpass and 340Hz lowpass constrain the output.
These filters and the profile's expected unfiltered RMS0.14 at full amount are
engineering voicing choices. Stochastic AM creates sidebands; carrier bounds and
measured output bandwidth are not a proof of strict analytic bandlimiting.

Offline fitting uses separately indexed A exterior, B cabin, D dyno and E cabin
segments after all four full media files were scanned. The observed L/R powers
are averaged, smoothed with a 6Hz Gaussian sigma, sampled onto the dense grid,
and given documented spectral tapers/level. This removes narrow-line identity;
the result is a recording-informed LF texture/PAD, not a waveform-exact engine
resynthesis or identified physical source. No inter-source transfer averaging is
performed. The four recorded perspectives remain separate profiles.

These recordings mix combustion, exhaust, body, road, air, microphones and space.
A bandpass reference does not separate those sources. Cabin/dyno profiles are
contrast options; A is the exterior default. Adding this independent source is
an intentional LF voicing supplement, not a decomposition of existing DNA LF.
Do not apply the recording's room or cabin response again by default. Absolute
RPM/load/state conditioning, broadband noise/NVH and 7.1.4 rendering remain outside
this module. Current technical checks do not establish subjective acceptance.
