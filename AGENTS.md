# Vehicle Sound Lab

- Build the current Windows system with `Build-System.ps1`; it runs 27 CTests, including new DNA/spatial and monitor contracts. Read `handoff/C模块与接口.md` for module boundaries.
- Preserve the frozen listening baselines and recorded takes. The driver’s legacy `.dna`, the sustained Sound DNA model, and the low rumble model are separate contracts.
- Keep drive state and controls, synthesis voices, spatial processing, and file/device I/O separate. Keep file I/O and allocations out of audio processing.
- Sound DNA V1 is accepted for one fixed V10 listening context. Low Rumble V2 is a rejected comparison. Both are independent of the driving DSP. Resume low frequency research using `handoff/研究续接.md`.
- Coherent LF V1 subsequently received fixed-context listening acceptance; see `research/coherent_low_v1_acceptance.json`. It uses Sound DNA models, not the rejected low-rumble model contract. Preserve the frozen experiment and record subsequent feedback separately. `modules/dna_scene` is an isolated new-DNA/spatial adapter, not wide-RPM driving coverage.
- `modules/scene_monitor` and `experiments/scene_monitor_v1` provide a new stereo device/UI host, defaulting to the accepted dry pair. Native device/control checks are technical evidence; spatial and new-host human listening remain pending. This host does not use legacy driving take files; its bounded control trace is debug evidence only.
- Keep recordings, external assets, old binaries, captures and archive payloads in the local handoff; Git tracks source, authored documentation and runtime model profiles.
- `voices/cabin_anchors_v1` contains two unaccepted E cabin anchors using four-cycle Hann analysis. They share the existing C codec, but are not phase-aligned for morphing or integrated into driving. Do not combine them with A exterior LF. Legacy compiler defaults and accepted models remain preserved; see `research/驾驶素材与DNA锚点V1.md` for shift/display evidence, analysis failures and bounds.
