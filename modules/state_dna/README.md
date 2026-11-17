# State DNA

Pure parameter synthesis for base, idle, power and overrun banks. This module owns no driver, device, PCM stream or spatial renderer.

- `bank.c`: prepare common cycle-origin alignment and L/R-preserving phase offsets on the union of anchor grids. Setup only; banks are borrowed immutable.
- `lookup.c`: locate anchors and interpolate their statistical harmonic magnitudes.
- `voice.c`: smooth state weights and synthesize with the supplied `SaVoice` phase, root, gain and frame counter. The main clock advances exactly once.

Call `sx_bank_init`, then `sx_voice_init` outside audio processing. Select a state with `sx_voice_select`; an absent donor selects base. Call `sx_voice_tick` once per main sample and query `sx_voice_telemetry` for availability, actual/target weights and each bank's frequency coverage. The host must serialize all access to one voice.

Each bank has 1–8 anchors. All banks must retain the same harmonic count; factor counts and anchor grids may differ. Statistical states keep advancing while inactive. Transitions use a 0.02–2 second first-order time constant, not a fixed-duration linear fade. Nonzero tails are expected after a state change.

The integration in `vehicle_source/state_dna.c` maps the existing driving states; authoring uses `vehicle_controller/dna_bank.py` schema2. This is an authorable state model, not evidence of measured physical RPM/load or source separation. No accepted catalog preset opts into this module automatically.
