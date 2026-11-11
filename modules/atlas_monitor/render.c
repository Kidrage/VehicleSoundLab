#include "render.h"
#include <string.h>
int am_render_init(AmRender *r,VslEngine *e,const AdConfig *c,const AdControl *p) {
    if(!r)return 0;
    memset(r,0,sizeof *r);return ad_render_init(&r->drive,e,c,p);
}
int am_render_set(AmRender *r,const AdControl *p) { return r&&ad_render_set(&r->drive,p); }
int am_render_process(AmRender *r,float *out,unsigned frames,int stop,const AdCapture *capture) {
    unsigned n;int c;
    if(!r||(stop!=0&&stop!=1)||!ad_render_process(&r->drive,out,frames,capture))return 0;
    for(n=0;n<frames;++n) {
        double gain=r->frame<480?(double)r->frame/480:1;
        /* Once transport release starts it cannot reverse; restart reinitializes
           a fresh simulation. Engine ignition remains a separate drive input. */
        if(stop||r->release) {
            if(r->release<480)++r->release;
            gain*=1-r->release/480.;
        }
        for(c=0;c<r->drive.config.channels;++c)out[n*r->drive.config.channels+c]*=(float)gain;
        ++r->frame;
    }
    return 1;
}
