#ifndef VSL_TAKE_FILE_H
#define VSL_TAKE_FILE_H
#include "session/take.h"
/* Non-realtime. UTF-8 paths. Load replaces an initialized (possibly zero) take
   only on full validation. Save atomically replaces the requested path. */
int vsl_take_save(const char *path,const VslTake *take);
int vsl_take_load(const char *path,VslTake *take);
#endif
