# A startup-settling cabin: stereo continuous detail candidate

`A cabin settle.sres` is a pure-parameter candidate fitted to approved A38.48–39.51s.
Use ONLY with the unchanged `startup_settle_v1/A start cabin settle.model` at its
observed acoustic base34.837537335058876Hz. This is not a new warm-idle/RPM or
exterior calibration, and has no listening acceptance or driving integration.

Eight continuous two-channel VAR24 filters, Cholesky innovations and SOS are
stored. The file contains no PCM or recorded coefficient timeline.600–850Hz
was excluded because its additive stereo covariance debt is indefinite; it
remains a measured gap, not a band to clip or fill with arbitrary EQ.

Text format: `VSL_STEREO_RESONANCE 1 RATE COUNT WARMUP BASE_HZ`, then per band
`ORDER SECTIONS LOW HIGH GAIN`, row-major `A[order][2][2]`, lower noise root2×2,
SOS[sections][6], and Lyapunov certificate[2*order][2*order]. Model/profile IO
is independent of the existing `.rdetail` and `.vslrun` schema6 contracts.

See [module interface](../../modules/stereo_resonance/README.md) and
[source/verification limits](../../research/低转双声道连续细节V1.md).
