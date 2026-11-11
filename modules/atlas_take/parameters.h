#ifndef VSL_ATLAS_TAKE_PARAMETERS_H
#define VSL_ATLAS_TAKE_PARAMETERS_H
#include "atlas_drive/control.h"
#include <stddef.h>
typedef struct { const char *name;size_t offset;int integer; } AtField;
const AtField *at_fields(unsigned *count);
int at_control_same(const AdControl *a,const AdControl *b);
#endif
