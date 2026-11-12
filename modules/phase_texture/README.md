# Shared phase texture

An optional adapter for an initialized, valid 48kHz `SdVoice`; it borrows the same immutable profile. The caller owns all state and must pass that same voice/profile for its lifetime.

- `motion.*`: independent stochastic control; fixed20–70Hz bandpass at187.5Hz, streamed natural spline, bounded4us displacement.
- `voice.*`: original magnitude statistics and clock, shared high-harmonic phase displacement. One motion for all harmonics and observation channels.
- `pt_voice_set(0..1)`: bypass through **light**2us design scale,18ms following. No deeper medium setting.
- At zero the original oscillator function runs, retaining exact output and `SdVoice` state. Motion keeps running while bypassed.

No PCM, recorded timeline, allocations, file/device I/O, driver, physical crank identification or spatial rendering. Existing `sound_dna` files remain unchanged. See [integration and evidence](../../research/共同微扰C接入V1.md).
