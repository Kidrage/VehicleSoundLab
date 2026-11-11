# Accepted64 reference OSC preview V2

The user selected the original64OSC timbre on2026-11-10. This experiment keeps
that base exact at unity pitch/high0, adds separately observed exterior HF,
and tests pitch independent of trajectory duration. It is a six-second fitted
parameter voice, not a sustained RPM/load engine model.

- `tracks.*`: persistent IDs, endpoint continuity checks, transactional loading.
- `pitch.*`: block-independent stereo OSC phase, smoothed pitch/high contribution.
- `audio.*`: float waveOut, completion events/MMCSS, no render-loop allocation/I/O.
- `ui.c`: small Windows preview with two sliders and play/stop.
- `probe.c`: offline float output; `checks.c`: independent analytic controls.
- `../reference_osc_v1/model.*` and `oscillator.*`: reused unchanged for loading/parity.

Build: `cmake -S experiments/reference_osc_v2 -B build-reference-osc-v2 -G "Visual Studio 17 2022" -A x64`, then `cmake --build build-reference-osc-v2 --config Release`.

Run `Launch-reference64.cmd` from the workspace. No autoplay. The GUI defaults
to pitch1/high0 and allows pitch.9..1.1/high0...5. New high is active only after
the catalogue-approved exterior interval begins in the archival timeline.

Models and ID maps must be immutable throughout a player's lifetime; init/load
and ownership operations are outside audio processing. Zero-initialize owning
objects; failed loads preserve existing data. The ID loader checks segment
shape, duplicate/reused IDs, matching amplitude/frequency/phase endpoints and
trailing content. `RtTracks` passed directly to a player must satisfy the same
validated contract. The player owns only its extra-phase state.

`research/旧64OSC高频V2.md` records sources, preprocessing, waveform alignment,
limits, device checks and the distinction from a general engine synth.
