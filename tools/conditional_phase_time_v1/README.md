# Conditional phase through the original observer

`mapping.py` evaluates the same continuous P-hat inverse CDF with only its two
nonzero rows. It must match every frozen 1025-point map probe before generation.
`generator.py` shares amplitudes/common phase across five alternatives and gives
conditional phase a separate, domain-separated Gaussian stream. Original AR
parameters are a diagnostic probe; they are not an identified engine time law.

`observer.py` calls the original Hann4096/hop256 harmonic observer. Its projected
line powers and separately normalized whole-window band powers are distinct.
`fixtures.py` supplies finite-tone/AM/PM/silence controls. No module owns a driver,
room, physical source position or PCM playback timeline.

Waveforms use 1024 samples per acoustic cycle directly. This isolates forward
observation without another resampler, but does not certify native48k aliasing,
listening naturalness, C performance or physical7.1.4. Existing runtime and
pending hearings remain unchanged.

`metrics.py` compares instantaneous coefficients, reobserved harmonic lines and
whole-band waves against their respective source targets. Source-row-count
chunks retain their unequal lengths (39..41 rows) and overlap; they are not
independent trials. Run/audit/review/package hosts remain separate from the
generation modules. The real audit regenerates both RNG/AR streams, all
instantaneous statistics, sparse scalar OSC samples and every STFT row without
importing the producer generator, decoder, observer or statistics functions.
