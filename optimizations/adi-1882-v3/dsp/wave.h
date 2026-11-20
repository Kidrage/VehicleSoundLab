#ifndef VSL_FAST_WAVE_H
#define VSL_FAST_WAVE_H
/* Linear interpolation; valid finite phase magnitude below 1e6 radians. */
float vsl_sine(float radians);
float vsl_cosine(float radians);
#endif
