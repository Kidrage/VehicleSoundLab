#ifndef VSL_OSC_COLOUR_PROFILE_H
#define VSL_OSC_COLOUR_PROFILE_H
#include <stdio.h>
#define OC_MAX_KNOTS 16
#define OC_MAX_HARMONICS 320
typedef struct {unsigned count;double order[OC_MAX_KNOTS],db[OC_MAX_KNOTS];} OcProfile;
int oc_profile_valid(const OcProfile *profile);
/* Non-RT, transactional, caller owns FILE. No PCM or phase coefficients. */
int oc_profile_read(FILE *stream,OcProfile *profile);
int oc_profile_compile(const OcProfile *profile,double *harmonic_gain,unsigned count);
#endif
