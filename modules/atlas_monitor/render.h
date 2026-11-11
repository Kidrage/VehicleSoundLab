#ifndef VSL_ATLAS_MONITOR_RENDER_H
#define VSL_ATLAS_MONITOR_RENDER_H
#include "atlas_drive/render.h"
typedef struct {
    AdRender drive;
    uint64_t frame;
    unsigned release;
} AmRender;
/* Transport fades only. The driving controller, source and spatial work remain
   in atlas_drive. Caller owns exclusive engine/bank/model storage. */
int am_render_init(AmRender *render,VslEngine *engine,const AdConfig *config,const AdControl *control);
int am_render_set(AmRender *render,const AdControl *control);
int am_render_process(AmRender *render,float *output,unsigned frames,int stop,const AdCapture *capture);
#endif
