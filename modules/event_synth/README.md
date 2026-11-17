# Procedural event source

Caller-owned, allocation-free event synthesis at 48 kHz. Four concurrent voices;
each profile has at most 12 damped sine modes, four procedural-noise resonant
bands and four optional amplitude contours. There is no PCM source, room model
or speaker routing. Scheduling policy lives in `event_control`.

`api.h` defines parameters and the pool API. `profile.c` validates them;
`pool.c` manages voice identity and bounded replacement/release; `voice.c`
combines oscillator, noise, coloration and envelope modules. `contour.c`
selects groups using nominal component frequency and interpolates 2–8 gain
knots. Contours replace the selected components' local attack/decay, retain
global fades, follow the request decay multiplier, and hold their last value.
Absent contours retain the original signal path.

See [V12 integration and evidence](../../handoff/启动多段包络与控制台V12.md).
