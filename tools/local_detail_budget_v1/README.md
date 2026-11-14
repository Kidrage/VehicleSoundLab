# Native stereo detail budget

Offline analysis only. `spectrum.py` contains finite-window power-matrix primitives and analytic controls. Producer, independent auditor, plotter and packager are separate entry points in the parent `tools` directory; no real-time C or audio parameters are changed.

Use `measure_F3_local_detail_budget_v1.py --workspace E:\VehicleSoundLab --out NEW_DIRECTORY`, then `audit_F3_local_detail_budget_v1.py --workspace ... --measure MEASUREMENT_DIRECTORY --out NEW_DIRECTORY`, followed by `review_F3_local_detail_budget_v1.py --workspace ... --measure ... --audit ... --out NEW_DIRECTORY`.

The authoritative fixed inputs, windows, thresholds and limitations are in `research/F3_local_detail_budget_v1_plan.json`. Matrices use `L*conj(R)`. Indefinite differences are saved literally; they are never normalized as if they were valid covariance matrices or silently clipped to permit a noise fit. Refer to `research/F3原生双声道细节预算V1.md` for findings and the next generation step.
