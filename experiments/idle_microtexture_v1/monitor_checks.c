#include "monitor.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line%u: %s\n",(unsigned)__LINE__,#x);return 1;}}while(0)
static FmModels model;
int main(void) {
    FmRender *a,*b;unsigned n,c;double amount=1,target=1,step=0;unsigned left=0;
    model.core.rate=48000;model.core.count=1;model.core.mode[0].hz=83.17;
    model.core.mode[0].amplitude[0]=.2;model.core.mode[0].amplitude[1]=.13;
    model.core.mode[0].phase[0]=.1;model.core.mode[0].phase[1]=.3;
    model.motion.rate=48000;model.motion.count=1;model.motion.hop_frames=17;model.motion.alpha=.7;model.motion.factor[0][0]=.1;
    model.fine.rate=48000;model.fine.count=1;model.fine.band[0].count=1;model.fine.band[0].taps[0]=1;
    model.fine.band[0].gain=0;model.fine.band[0].right_over_left=.7;
    a=fm_render_create(&model,149921,.5);b=fm_render_create(&model,149921,.5);CHECK(a&&b);
    {float out[2];CHECK(!fm_render_tick(a,NAN,1,.5,.25,out)&&!fm_render_tick(a,1,1,1.1,.25,out)&&!fm_render_tick(a,1,1,.5,.25,NULL));}
    for(n=0;n<5001;++n) {
        float x[2],y[2];double wanted=n>=3001?1:n>=1201?0:1;
        if(wanted!=target){target=wanted;left=864;step=(target-amount)/864;}
        if(left){if(!--left)amount=target;else amount+=step;}
        CHECK(fm_render_tick(a,wanted,1,.5,.251188643150958,x)&&fm_render_tick(b,wanted,1,.5,.251188643150958,y));
        CHECK(!memcmp(x,y,sizeof x));
        for(c=0;c<2;++c) {
            double exact=model.core.mode[0].amplitude[c]*cos(2*3.14159265358979323846*83.17*n/48000+model.core.mode[0].phase[c])*amount*.251188643150958;
            CHECK(fabs(x[c]-exact)<1e-8);
        }
    }
    fm_render_destroy(a);fm_render_destroy(b);puts("fast_idle_monitor_controls_passed=1");return 0;
}
