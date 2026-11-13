#ifndef VSL_MODAL_TEXTURE_IO_H
#define VSL_MODAL_TEXTURE_IO_H
#include "profile.h"
#include <stdio.h>
/* Non-RT strict versioned text input. Failure leaves output untouched. */
int mt_profile_read(FILE *file,MtProfile *profile);
int mt_profile_load(const char *path,MtProfile *profile);
#endif
