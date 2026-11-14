# Seeded raw Sound DNA export

Offline host for the unchanged `modules/sound_dna` kernel. Build this directory
with CMake. The existing monitor probe remains unchanged: its final argument is
a raw/monitor selector and its seed is fixed at `SM_SEED=48271`.

```
sound_dna_export model out.wav seconds pitch detail seed block_frames
```

`seed` is an explicit nonzero uint64 decimal; `block_frames` is 1..512. Pitch is
0.9..1.1, detail 0..1, duration at most 60 seconds. Output is stereo 48 kHz FLOAT,
unity gain, with no onset fade, peak normalization, PCM loop, room or limiter.
This host does not change the driving runtime or promote any source model.
