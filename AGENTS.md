# Vehicle Sound Lab

- Build the current Windows system with `Build-System.ps1`; it runs the 25 CTests. Read `handoff/C模块与接口.md` for module boundaries.
- Preserve the frozen listening baselines and recorded takes. The driver’s legacy `.dna`, the sustained Sound DNA model, and the low rumble model are separate contracts.
- Keep drive state and controls, synthesis voices, spatial processing, and file/device I/O separate. Keep file I/O and allocations out of audio processing.
- Sound DNA V1 is accepted for one fixed V10 listening context. Low Rumble V2 is a rejected comparison. Both are independent of the driving DSP. Resume low frequency research using `handoff/研究续接.md`.
- Keep recordings, external assets, old binaries, captures and archive payloads in the local handoff; Git tracks source, authored documentation and runtime model profiles.
