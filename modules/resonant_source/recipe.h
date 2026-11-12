#ifndef VSL_RESONANT_SOURCE_RECIPE_H
#define VSL_RESONANT_SOURCE_RECIPE_H
#include "sound_dna/profile.h"
typedef struct { double power_reduction,low_hz,high_hz; } RssColour;
/* Non-RT. Same numeric bounds as the SOUND_DNA file contract. */
int rss_profile_valid(const SdProfile *profile);
/* Non-RT, transactional; output and original must be distinct.
   Positive common gains preserve mean phase, dimensions and AR correlations. */
int rss_profile_prepare(SdProfile *output,const SdProfile *original,const RssColour *colour);
#endif
