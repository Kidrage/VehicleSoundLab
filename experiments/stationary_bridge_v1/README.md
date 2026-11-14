# Stationary bridge candidate

An offline host for the original four stationary DNA anchors plus the one
new source-qualified middle observation. It uses the original controller,
atlas, detail, recipe, monitor and owned-take modules. No runtime DSP changes.
Two requested extra observations failed the original independent-carrier gate
and have no published models. The seven-anchor plan was not achieved.

Build from the repository root:

```powershell
cmake -S experiments/stationary_bridge_v1 -B build-stationary-bridge-v1 -A x64
cmake --build build-stationary-bridge-v1 --config Release --target stationary_bridge_probe
```

Run from the repository root with an unused output prefix in an existing folder:
`stationary_bridge_probe PREFIX VARIANT SCENE CHANNELS BLOCK`.
Variants 0/1/2 mean DNA / detail configured at zero / candidate; scenes are
`neutral` (12s) or `shifts` (16s), channels 2 or 12, block 1..240.
This host follows the previous stationary recipe experiment's small export
harness. Each experiment retains its own immutable asset assembly; all sound,
driver and take algorithms remain in the shared modules.

Use `tools/verify_stationary_recipe_v1.py` with
`--source-dir experiments/stationary_bridge_v1` for the new bank. The optional
argument selects the source snapshot, not the synthesis or checks.

The RPM-to-acoustic-root mapping is still an engineering 1/120 hypothesis.
Source windows are falling-rev observations, not measured RPM/load points.
No native default, realtime-device, other-engine or physical 7.1.4 acceptance.
See `research/驻车中间声线V1.md` and its linked audition.
