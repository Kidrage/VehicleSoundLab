# Full spectral-budget event research

Offline source-free event generator; it does not replace the shipping C event
ABI, controller or authoring UI. It accepts the existing modal frequency/phase
profile and adds six independently coloured procedural-noise branches covering
the complete spectrum. Both modal and noise envelopes are editable.

- `filters.py`: AR/SOS colour, explicit lowpass/bandpass/highpass, stationary budget.
- `profile.py`: sparse parameter contract and at most80 amplitude controls.
- `measure.py`: six-band mean-channel-power observations.
- `design.py`: one source-derived modal/noise budget initializer.
- `voice.py`: independent generated innovations, oscillator amplitudes, release.
- `fit.py`: exact finite-waveform powers, feasible-start guard, one objective solve.

Profiles store coefficients and amplitude knots, never PCM. New excitations are
generated for each seed. The prototype has one second of offline procedural
prewarm; realtime trigger initialization is not implemented. All processing is
mono source generation, without a room or speaker renderer.

Known coverage, finite response, derivatives, feasible and infeasible paths pass.
The real crank candidate improves the training weighted shape error by55%, but
fails held-out checks. Catch fails the feasibility guard. Neither is a usable
voice. See `handoff/启动全频预算与可行性检查V1.md` for the identified modal-capacity
limit and the required next source analysis.
