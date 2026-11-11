#ifndef VSL_ATLAS_TAKE_IO_H
#define VSL_ATLAS_TAKE_IO_H
#include "atlas_take/take.h"
#include <stddef.h>
#define AT_FILE_LIMIT (32u*1024u*1024u)
/* All APIs are non-RT. Decode/load preserve an initialized destination on failure.
   Encode returns malloc storage; caller frees it. File paths are UTF8. */
int at_take_encode(const AtTake *take,unsigned char **bytes,size_t *length);
int at_take_decode(AtTake *take,const unsigned char *bytes,size_t length);
int at_take_save(const AtTake *take,const char *path);
int at_take_load(AtTake *take,const char *path);
#endif
