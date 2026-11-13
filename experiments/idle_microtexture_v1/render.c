#include "monitor.h"
#include "modal_source/voice.h"
#include "spectral_motion/voice.h"
#include <math.h>
#include <stdlib.h>
struct FmRender {MsVoice core;SpmVoice *detail;MsRamp main_amount,detail_amount,level;};
static int unit(double x){return isfinite(x)&&x>=0&&x<=1;}
static double ramp(MsRamp *r,double target) {
    if(target!=r->target){r->target=target;r->left=MS_RAMP_FRAMES;r->step=(target-r->value)/MS_RAMP_FRAMES;}
    if(r->left){if(!--r->left)r->value=r->target;else r->value+=r->step;}return r->value;
}
void fm_render_destroy(FmRender *r){if(r){spm_voice_destroy(r->detail);free(r);}}
FmRender *fm_render_create(const FmModels *models,uint64_t seed,double grain) {
    FmRender *r;SpmProfile p;unsigned i;
    if(!models||models->motion.count>models->fine.count)return NULL;
    p.spectral=&models->fine;p.motion=&models->motion;
    for(i=0;i<SF_MAX_BANDS;++i)p.map[i]=0;
    for(i=0;i<models->motion.count;++i)p.map[models->fine.count-models->motion.count+i]=i+1;
    r=calloc(1,sizeof *r);if(!r)return NULL;
    if(!ms_voice_init(&r->core,&models->core,1,1)||!(r->detail=spm_voice_create(&p,seed,grain))){fm_render_destroy(r);return NULL;}
    r->main_amount.value=r->main_amount.target=r->detail_amount.value=r->detail_amount.target=1;
    r->level.value=r->level.target=.251188643150958;return r;
}
int fm_render_tick(FmRender *r,double main,double detail,double grain,double level,float out[2]) {
    double m[2],d[2],a,b,g;unsigned c;
    if(!r||!out||!unit(main)||!unit(detail)||!unit(grain)||!unit(level))return 0;
    if(!spm_voice_set(r->detail,grain)||!ms_voice_tick(&r->core,m)||!spm_voice_tick(r->detail,d,NULL))return 0;
    a=ramp(&r->main_amount,main);b=ramp(&r->detail_amount,detail);g=ramp(&r->level,level);
    for(c=0;c<2;++c){double x=(m[c]*a+d[c]*b)*g;if(!isfinite(x)||fabs(x)>3.4e38)return 0;out[c]=(float)x;}
    return 1;
}
void fm_check_controls(uint64_t n,double *main,double *detail,double *grain,double *level) {
    *main=1;*detail=1;*grain=.5;*level=.251188643150958;
    if(n>=12001)*grain=1;
    if(n>=24013)*detail=.4;
    if(n>=39031)*main=0;
    if(n>=48017)*grain=0;
    if(n>=60019)*detail=1;
    if(n>=72023)*main=1;
    if(n>=84029)*grain=.5;
}
