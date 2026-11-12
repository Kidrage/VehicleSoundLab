#ifndef VSL_RESONANT_DETAIL_IO_PROFILE_H
#define VSL_RESONANT_DETAIL_IO_PROFILE_H
#include "resonant_detail/profile.h"
#include <stdio.h>
/* Non-RT file parsing, transactional: output unchanged on failure. */
int rdt_profile_read(FILE *stream,RdtProfile *profile);
int rdt_profile_load(const char *utf8_path,RdtProfile *profile);
#endif
