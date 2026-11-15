# Carrier transfer diagnostic

Repartition exact frozen oscillator contributions by nominal carrier frequency.
This is an offline diagnostic, not an engine-source separator or new preset.

- `groups.py`: nominal carrier tags and boundaries.
- `replay.py`: original frozen states, mappings and oscillator sums by group.
- `spectral.py`: full complex group/channel Gram matrices and signed identities.
- `fixtures.py`: analytic tones, AM/PM sidebands, interference and silence.
- `metrics.py`: source-normalized budgets, complex L/R and paired changes.

Run, independent known/real audit, published-metrics audit, plots and packaging
have separate entry points in the parent `tools` folder. Recordings, arrays,
exact executed sources and figures stay in the data workspace.

Keep all signed cross terms. Ratios to original band powers or generated total
are descriptive diagnostics, not physical contribution percentages. Six source
contexts and three seeds are not independent engine recordings. See
`research/载频来源与高频扩散V1.md` and the frozen plan.
