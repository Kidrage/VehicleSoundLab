#ifndef VSL_RENDER_SESSION_H
#define VSL_RENDER_SESSION_H
#include "core/engine.h"
int vsl_render_file(const char *path,const VslParams *params,double seconds,int drive,const char *dna,const char *ir);
int vsl_render_session(const char *path,const VslParams *params,double seconds,int drive,
    const char *dna,const char *ir,int channels,const char *trace_path,const char *stem_prefix);
#endif
