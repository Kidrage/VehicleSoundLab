# Common and relative stereo phase

An offline extension of the source-derived statistical OSC model. No runtime C,
catalog, driver, room, takes or accepted preset is changed.

| Module | Responsibility |
|---|---|
| `coordinates.py` | Per-harmonic symmetric phase midpoint and L-minus-R phase difference; circular branches and decoding |
| `profile.py` | Original amplitude quantiles and joint normal-rank/PCA/diagonal-residual/AR compiler, using the new coordinates |
| `observe.py` | Relative circular moments and the signed amplitude-product/phase association |
| `render.py` | Pair of fixed-phase and varying-phase OSC outputs from one shared amplitude evaluation |
| `review.html` | One player with paired variants and independent raw reference |

Generation reuses `radial_copula_v1/latent.py` and `quantiles.py`. Compilation is
offline; the sorted quantiles contain no original sample or coefficient timeline.
The common coordinate is per harmonic, not a single LFO applied to every order,
and not the earlier shared-microperturbation preset. Observed stereo is not a
physical left/right cylinder-bank decomposition.

Run, numeric audit, paired rendering, audio audit, review, review-metric audit and
freezing have separate hosts in `tools/*relative_phase_v1.py`. Read the fixed
numeric and audio plans in `research/` first. No rank/rho/strength search is used.

The new coordinate system improves six training observations' complex stereo
coherence, but five coordinates still regress against fixed phase; the generated
time law remains approximate. This is not timbre acceptance, a target C port or
full driving/multi-engine/physical7.1.4 coverage. A future port must join the same
single driver and separate spatial API, with its own numerical, CPU and listening
qualification. Audio-rate projection is not covered by the old21569 budget.
