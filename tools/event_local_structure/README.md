# Local event structure

Offline native-resolution peak inventories, finite half-power widths, mutually
unique adjacent correspondences and window-centre phase observations. No source
fit, synthesizer, physical classifier or automatic RPM inference.

`spectrum.py` owns finite FFT/channel powers/widths. `links.py` preserves absent
and ambiguous matches, never bridges gaps, and keeps phase evidence separate
from geometric matching. `inspect.py` composes a resolution/hop observation.

Compare nonoverlap and quarter-window hops. Shared samples can create apparent
phase memory; finite resonant noise can also create narrow, persistent peaks.
Chirp broadening and the finite Hann main lobe confound width. A modulus computed
from a finite set of selected phase differences is descriptive, not measured
physical coherence or probability of oscillator identity. Full0–24k channel
power remains available even though the peak inventory ends at14kHz.
