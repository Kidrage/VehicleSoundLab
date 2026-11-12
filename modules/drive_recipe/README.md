# Driving recipe adapter

Retains the existing moving35 DNA + coherent LF + continuous-detail recipe in
the same atlas driver. It does not fit new timbres or add a second RPM clock.

| Files | Responsibility |
|---|---|
| `bank.*` | Non-RT transactional ownership of optional LF profiles, scales, local bounds and compiled harmonic power reductions; validates matching detail anchors |
| `shape.*` | Predict the next main-voice root and detail amount; withdraw harmonic power only where the corresponding detail is active |
| `voice.*` | Continuous LF statistics and oscillators, synchronized each sample to the main DNA's captured phase plus anchor origin; independent smoothed amount |

`drc_shape` precedes the main sample; `drc_voice_tick` follows it. Power shape is
`sqrt(1 - sum(weight * support² * detail_amount² * reduction))`. Detail at zero
or outside its local bounds restores the original DNA. LF is a separate fitted
source, not `harmonic_body`'s complementary tap. Its gain and driving body
envelope are independent. Internal statistics keep advancing while muted.

The new adapter has no runtime allocation, file I/O, room, device or controller.
`atlas_drive` handles envelopes/mixing/routing; `atlas_take` owns all parameters
and `atlas_take_io` serializes them in schema8. The native host uses its existing
sliders, record/save/load controls and the same driver.

The retained real recipe is one exterior acoustic anchor at46.875Hz,7 LF
harmonics, original scale1.6658265329883064 and the unchanged moving_35 detail.
The .9–1.1 support is an engineering fade, not measured RPM/load coverage.
No new warm-idle/acceleration or multi-engine timbre acceptance follows from
the three-seed recipe oracle and synthetic two-anchor reuse checks.
