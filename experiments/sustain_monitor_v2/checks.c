#include "render.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
static LbProfile body;static SuModel model;static SuSource source;static SmRender a,b;
int main(int argc,char **argv){
    unsigned i,at,n;float raw[2048],out[2048],other[2048],other_out[2048];double ref[2048];
    if(argc!=3||!lb_profile_load(argv[2],&body)||!su_model_load(argv[1],&model)||!sm_render_init(&a,&model,1000,1000,0)||!sm_render_init(&b,&model,1000,1000,0)||!su_init(&source,&model,SM_SEED,1,1,1))return 1;
    su_process(&source,ref,1024);sm_render_process(&a,raw,out,1024,0);
    for(at=0;at<1024;at+=n){n=1024-at;if(n>73)n=73;sm_render_process(&b,other+at*2,other_out+at*2,n,0);}
    if(memcmp(raw,other,sizeof raw)||memcmp(out,other_out,sizeof out))return 2;
    for(i=0;i<2048;++i)if(raw[i]!=(float)ref[i]||!isfinite(out[i]))return 3;
    if(out[0]!=0||out[1]!=0)return 4;
    for(i=480;i<2048;++i)if(out[i]!=(float)(ref[i]*.5))return 5;
    if(sm_render_set(&a,899,1000,0)||sm_render_set(&a,1000,1001,0)||sm_render_set(&a,1000,1000,-19))return 6;
    if(!sm_render_set(&a,1100,0,-6))return 7;
    for(i=0;i<20;++i)sm_render_process(&a,raw,out,512,0);
    if(a.source.pitch<1.099||a.source.amount>.001||fabs(a.attenuation-pow(10,-6/20.))>.001)return 8;
    sm_render_process(&a,raw,out,512,1);
    if(a.release!=480)return 9;
    for(i=960;i<1024;++i)if(out[i]!=0)return 10;
    if(!sm_render_init(&a,&model,1000,1000,0)||!sm_render_init(&b,&model,1000,1000,0)||!sm_render_body_init(&a,&body,0))return 11;
    sm_render_process(&a,raw,out,1024,0);sm_render_process(&b,other,other_out,1024,0);
    if(memcmp(raw,other,sizeof raw)||memcmp(out,other_out,sizeof out))return 12;
    if(!sm_render_body_amount(&a,.8)||!sm_render_set(&a,900,1000,0))return 13;
    for(i=0;i<50;++i)sm_render_process(&a,raw,out,512,0);
    if(a.body.amount<.799||fabs(a.body.phase-a.source.phase)>1e-12)return 14;
    for(i=0;i<1024;++i)if(!isfinite(out[i]))return 15;
    puts("monitor: frozen-source parity, block invariance, onset/stop, attenuation/control smoothing and validation pass");return 0;
}
