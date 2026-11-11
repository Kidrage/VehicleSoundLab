# Vehicle Sound Lab

- Build the current Windows system with `Build-System.ps1`; it runs 26 CTests, including the new DNA/spatial adapter. Read `handoff/C模块与接口.md` for module boundaries.
- Preserve the frozen listening baselines and recorded takes. The driver’s legacy `.dna`, the sustained Sound DNA model, and the low rumble model are separate contracts.
- Keep drive state and controls, synthesis voices, spatial processing, and file/device I/O separate. Keep file I/O and allocations out of audio processing.
- Sound DNA V1 is accepted for one fixed V10 listening context. Low Rumble V2 is a rejected comparison. Both are independent of the driving DSP. Resume low frequency research using `handoff/研究续接.md`.
- Coherent LF V1 subsequently received fixed-context listening acceptance; see `research/coherent_low_v1_acceptance.json`. It uses Sound DNA models, not the rejected low-rumble model contract. Preserve the frozen experiment and record subsequent feedback separately. `modules/dna_scene` is an isolated new-DNA/spatial adapter, not wide-RPM driving coverage.
- Keep recordings, external assets, old binaries, captures and archive payloads in the local handoff; Git tracks source, authored documentation and runtime model profiles.
