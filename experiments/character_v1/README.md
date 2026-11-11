# Character V1 · offline audition host

See [implementation and listening notes](../../research/燃烧与机械细节实验V1.md).

This is an isolated engineering audition, not a V015 runtime update. Its
single-threaded host binds one experiment state to one engine at a time. CMake
copies the exact frozen V015 sample dispatcher into the build folder and adds
one hook before the source IR. All other runtime objects come from the frozen
library. No source reference audio is played by either candidate.

Pressure response, structure response, profile data, event orchestration, file
hosting and verification remain separate modules. A future production version
must put per-instance state and explicit parameters inside the normal engine,
preset and take protocols; the global offline binding is not an audio API.

Input takes remain original V015 data and fingerprints. Candidate exports are
explicitly experimental WAVs with analysis metadata, never new V015 takes.
