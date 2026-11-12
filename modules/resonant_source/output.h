#ifndef VSL_RESONANT_SOURCE_OUTPUT_H
#define VSL_RESONANT_SOURCE_OUTPUT_H
#include "voice.h"
#include "stereo_bed/route.h"
/* Preallocated2/12output; observation L/R routed once to FL/FR. Other10zero.
   Master gain and width applied once; no inferred upmix, room or limiter. */
int rss_output_frame(const SbLayout *layout,const RssFrame *frame,double gain,double width,double *output);
#endif
