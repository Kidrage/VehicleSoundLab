# Harmonic body partition

Portable C11, allocation-free stereo LF bus. `band.*` selects existing harmonic
contributions with a smooth20→35Hz entry and180→350Hz exit. It introduces no
phase rotation, delay, extra oscillators, noise stream or recording playback.
`dna_atlas::sa_voice_tick_body` emits the complete original source and its LF
tap from the same harmonic samples. It does not advance a second clock.

`mix.*` moves that tap between two envelopes:

```
DNA = (full − amount × LF) × DNA envelope
body = amount × LF × body envelope × scale
```

The independent amount and body envelope follow18ms. Returning amount to0
snaps only below1e−12, restoring the exact old bypass after settling. Zero at
initialization always uses the original arithmetic. With equal effective
envelopes and scale1, the two buses reconstruct the original mixture to float
rounding for every amount. Different state envelopes intentionally rebalance
LF; there is no blanket additive doubling.

The driving adapter currently uses the existing `voice.body_gain`, scale1.6,
and a0..1 `body_mix` defaulting to0. These are engineering voicing choices,
not measured Lamborghini body transfer or torque-cut timing. Raw observation
L/R remain available; the spatial layer projects the bus to a BODY proxy once.
That proxy is not proof of a physically separated engine/block source.

This partition exposes LF already present in measured Sound DNA anchors.
It does not recover omitted cabin sub-bass, inharmonic LF, intake, mechanics,
or a new independent stochastic body source. Accepted moving-tailpipe A LF
and the historical rejected low-rumble models keep their separate contracts.
