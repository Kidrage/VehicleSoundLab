#ifndef VSL_STEREO_RESONANCE_IO_H
#define VSL_STEREO_RESONANCE_IO_H
#include "stereo_resonance/profile.h"
/* File IO, allocation and stability validation are non-RT. Transactional. */
int rvs_profile_load(const char *path,RvsProfile *profile);
#endif
