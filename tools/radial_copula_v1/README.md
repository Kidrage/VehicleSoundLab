# Radial / circular copula OSC candidate

An isolated offline statistical Sound DNA representation. It reuses frozen observations and the existing OSC order/taper convention; it does not replace C, the catalog, driver, owned takes, room processing or accepted presets.

| Module | Contract |
|---|---|
| `quantiles.py` | Continuous empirical amplitude/phase inverse CDFs. Analytic amplitude scaling preserves each partial/channel's mean squared amplitude. Phase changes cannot change this amplitude. |
| `profile.py` | Tie-aware normal ranks, joint L/R amplitude+phase PCA and diagonal residual, separately fitted factor/residual AR coefficients. Sorted marginal tables contain no original chronology. |
| `latent.py` | Fresh PCG64 Gaussian innovations, stationary AR endpoints, per-factor variance normalization during interpolation. No fixed LFO or coefficient-sequence loop. |
| `render.py` | Offline fixed acoustic-root OSC source, same 288 orders and19.2–21.6k taper; selectable original fixed phases versus new phase distribution. No driver clock, room or extra HF generator. |
| `observe.py` | Coefficient-power moments, complex L/R coherence and adjacent-row power products. These are not native acoustic power or physically separated source claims. |

The two new sound variants share identical amplitudes and random draws. Phase variation is a diagnostic: its current absolute L/R phase parameterization does not yet recover source stereo coherence. Do not promote it based on marginal power success.

`run_`, `audit_`, `review_`, `check_` and `package_radial_copula_v1` separate execution, independent numerical checks, one-player same-gain audition, muted browser QA and freezing. Read `research/radial_copula_v1_plan.json` before reproducing.

Known controls include PM with no AM, AM with no phase motion, circular wrap, opposed stereo amplitude and silence. The independent auditor uses piecewise quadrature, tie ranks, separate AR filtering, inverse-erf probabilities, scalar interpolated quantiles and direct trigonometric sums. FLOAT output checks include its explicit half-ULP rounding allowance.

This is not the rejected A harmonic-magnitude50/100 model: it uses six F3 observations, empirical positive radial distributions and a distinct joint circular representation; no old A magnitude asset is reused. New listening evidence is still required. Other engines, full-state driving calibration and physical7.1.4 remain active work. An eventual C port needs its own typed profile, numerical/CPU/listening validation and integration through the existing single driver.
