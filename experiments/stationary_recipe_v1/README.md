# Stationary recipe candidate

This offline host loads the original four A stationary DNA anchors and three
new, independently fitted detail profiles. The low anchor has no new detail.
It calls the existing controller, atlas, resonance, recipe, monitor and take
modules. It does not change the native UI or any accepted default.

Build from the repository root with `cmake -S experiments/stationary_recipe_v1
-B build-stationary-recipe-v1 -A x64`, then `cmake --build
build-stationary-recipe-v1 --config Release --target stationary_recipe_probe`.

CLI: `stationary_recipe_probe PREFIX VARIANT SCENE CHANNELS BLOCK`.
Use an unused output prefix in an existing directory. Variants are 0 original
DNA, 1 configured recipe at zero amount, 2 candidate at full amount. Supported
audition scenes are `neutral` (12 seconds) and `shifts` (16 seconds); channels
are 2 or 12, block is 1..240. WAV, detail WAV, dry layer floats, telemetry CSV,
owned `.vslrun` and result JSON share the prefix.

The scene sends pedal/gear controls; it never writes simulated RPM. Its mapping
of RPM to acoustic root remains the original engineering 1/120 hypothesis.
These are not synchronized replicas of the source video. File I/O is in this
offline host; no new realtime/device timing claim is made.

Run `tools/verify_stationary_recipe_v1.py --help` for the actual bypass,
chunk/layout, trajectory and old-player replay checks. Full provenance and
listening limits are in `research/驻车共振细节与驾驶V1.md`.
