# Event band texture research

Offline Python prototype; not attached to the controller, authoring UI or C ABI.
It retains the old modal component and replaces procedural noise with four
independent source-coloured SOS chains, each followed by its own amplitude
envelope. Profiles contain coefficients and eight time/gain knots per band,
never recording samples. There is no room or object rendering.

- `profile.py`: parameter validation, source PSD colour design, parameter vectors.
- `voice.py`: independent generated innovations, filter state, envelopes and release.
- `fit.py`: exact finite-waveform quadratic responses and bounded authoring solves.

The prototype uses one second of generated prewarm per band. That is offline
initialization, not a demonstrated realtime event-trigger strategy. No ADI
cost or runtime suitability is claimed. The old C event renderer remains the
baseline. Both real-source candidates failed, including the separately
declared conditioned-coordinate experiment; neither is an available timbre.

See `handoff/启动独立频带声源研究V1.md` and the corresponding verification JSON.
