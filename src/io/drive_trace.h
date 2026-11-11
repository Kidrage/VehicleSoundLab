#ifndef VSL_DRIVE_TRACE_H
#define VSL_DRIVE_TRACE_H
#include "core/types.h"
#include <stdio.h>
void vsl_trace_header(FILE *file);
void vsl_trace_frame(FILE *file,const VslEngine *engine,double seconds);
#endif
