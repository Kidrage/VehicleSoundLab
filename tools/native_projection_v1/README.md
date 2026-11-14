# Native conditional projection

Offline diagnostic modules: `projection.py` implements generic observed-coordinate inversion and QR; `budget.py` retains complete harmonic/remainder/cross matrices per native window; `controls.py` creates the declared exact mixtures. Nothing is attached to the real-time driver.

Run `tools/run_F3_native_projection_v1.py --workspace E:\VehicleSoundLab --out NEW_DIRECTORY`, then `tools/audit_F3_native_projection_v1.py --workspace ... --study ... --out NEW_DIRECTORY` and the corresponding `review_` tool. Inputs and gates are fixed in `research/F3_native_projection_v1_plan.json`.

Numerical projection passed. The source remainder is **not qualified as an independent detail target**: deterministic AM and finite noise enter the decomposition, and frequency-local H/R cross terms can strongly cancel. Never clip those terms, label the remainder isolated mechanical noise or use a smaller amount as a workaround. Findings and the next native-frequency route are in `research/F3原生投影与细节交叉项V1.md`.
