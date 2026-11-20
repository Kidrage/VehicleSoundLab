#ifndef VSL_SPECTRAL_TEXTURE_IO_H
#define VSL_SPECTRAL_TEXTURE_IO_H
#include "profile.h"
#include <stdio.h>
/* Non-RT, strict versioned input and heap temporary; failure preserves out. */
int sf_profile_read(FILE *file,SfProfile *out);
int sf_profile_load(const char *path,SfProfile *out);
#endif
