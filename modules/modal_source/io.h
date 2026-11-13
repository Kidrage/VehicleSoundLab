#ifndef VSL_MODAL_SOURCE_IO_H
#define VSL_MODAL_SOURCE_IO_H
#include "profile.h"
#include <stdio.h>
/* Non-RT only, transactional, strict EOF after one bounded profile. */
int ms_profile_read(FILE *stream,MsProfile *profile);
int ms_profile_load(const char *utf8_path,MsProfile *profile);
#endif
