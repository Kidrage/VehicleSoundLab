# Conditional phase slope optimization

`linear.py` fits the existing conditional CDF class at the frozen parent moment
target, with its declared finite precision. It keeps amplitude products, continuous
hat weights, phase-cell marginal and the positivity floor. All canonical matrices
and dual certificates remain checkable; solver-side coefficient truncation is not
treated as the original LP.

Offline dual objectives use 100-digit decimal products and accumulation because
large signed terms can cancel to a small objective. Acceptance uses the absolute
gap; the raw float64 signed gap is retained as a diagnostic. The separate auditor
reconstructs the objective with exact binary-rational arithmetic. Neither method
is a proposed realtime DSP kernel or a relaxation of the certificate gate.

The first LP maximizes `kappa` with `cell_probability >= kappa*phase_width`.
Because probabilities interpolate linearly between P nodes, `1/kappa` bounds the
inverse-CDF uniform derivative throughout the continuous P range. The second LP
keeps this density within a recorded numerical allowance and minimizes adjacent
row CDF gradients. This controls a conservative combined bound; it does not
guarantee improvement of every direct P derivative or every input path.

`measure.py` evaluates the direct bounds and identical unitless deterministic
paths. Those paths have no inferred RPM, audio rate or engine time constant.
No new audio, C voice, driver or spatial/room ownership is introduced. A future
candidate must still pass generation through the original observer, listening and
target CPU checks inside the existing V6 layers and one-driver architecture.
