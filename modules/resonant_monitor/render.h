#ifndef VSL_RESONANT_MONITOR_RENDER_H
#define VSL_RESONANT_MONITOR_RENDER_H
#include "resonant_source/output.h"
typedef struct {RssControl source;double gain,width;} RsmControl;
typedef struct {
    RssVoice voice;SbLayout layout;RsmControl target;
    double gain,width,follow;uint64_t frame;unsigned release;
} RsmRender;
typedef struct {float *dna,*low,*detail,*dry;} RsmCapture;
int rsm_control_valid(const RsmControl *control);
/* Non-RT: validates/warms source, transactional; borrowed models must outlive it. */
int rsm_render_init(RsmRender *render,const RssConfig *config,unsigned channels,const RsmControl *control);
int rsm_render_set(RsmRender *render,const RsmControl *control);
/* RT owner. dry is pre-transport layout output; other captures are pre-master
   calibrated stereo layers.10ms onset/release only, no room/limiter/I/O/alloc.
   A stop is irreversible until reinit; clocks continue through the fade. */
int rsm_render_process(RsmRender *render,float *output,unsigned frames,int stopping,const RsmCapture *capture);
#endif
