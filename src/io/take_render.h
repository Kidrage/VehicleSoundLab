#ifndef VSL_TAKE_RENDER_H
#define VSL_TAKE_RENDER_H
#include "session/take.h"
/* Float32 output at original DSP level; no export fade/normalization. Stereo
   hash verifies reconstruction before writing; multichannel retains sources. */
int vsl_take_render(const VslTake *take,const char *wav,int channels,const char *trace,const char *stems,uint64_t *hash);
#endif
