#include "voice.h"
#include <math.h>
#include <string.h>
#define MS_PI 3.14159265358979323846
static int valid(double r,double g){return isfinite(r)&&r>=.25&&r<=4&&isfinite(g)&&g>=0&&g<=1;}
static double taper(double hz) {
    double x;
    if(hz<=19200)return 1;
    if(hz>=21600)return 0;
    x=(hz-19200)/2400;return 1-x*x*(3-2*x);
}
static void rotations(MsVoice *v) {
    unsigned k;
    for(k=0;k<v->profile->count;++k) {
        double hz=v->profile->mode[k].hz*v->ratio.value;
        double angle=2*MS_PI*fmod(hz/MS_RATE,1);
        v->dc[k]=cos(angle);v->ds[k]=sin(angle);v->weight[k]=taper(hz);
    }
    v->rotation_ratio=v->ratio.value;
}
static void adopt(MsRamp *r,double target) {
    if(target==r->target)return;
    r->target=target;r->left=MS_RAMP_FRAMES;r->step=(target-r->value)/MS_RAMP_FRAMES;
}
static void advance(MsRamp *r) {
    if(r->left){if(!--r->left)r->value=r->target;else r->value+=r->step;}
}
int ms_voice_init(MsVoice *out,const MsProfile *p,double ratio,double gain) {
    MsVoice v;unsigned k,c;
    if(!out||!valid(ratio,gain)||!ms_profile_valid(p))return 0;
    memset(&v,0,sizeof v);v.profile=p;
    v.ratio.value=v.ratio.target=ratio;v.gain.value=v.gain.target=gain;
    for(k=0;k<p->count;++k) {
        v.cosine[k]=1;
        for(c=0;c<2;++c) {
            double phase=remainder(p->mode[k].phase[c],2*MS_PI);
            v.re[k][c]=p->mode[k].amplitude[c]*cos(phase);
            v.im[k][c]=p->mode[k].amplitude[c]*sin(phase);
        }
    }
    rotations(&v);*out=v;return 1;
}
int ms_voice_set(MsVoice *v,double ratio,double gain) {
    if(!v||!v->profile||!valid(ratio,gain))return 0;
    adopt(&v->ratio,ratio);adopt(&v->gain,gain);return 1;
}
int ms_voice_tick(MsVoice *v,double out[2]) {
    unsigned k,c;double result[2]={0,0};
    if(!v||!v->profile||!out)return 0;
    advance(&v->ratio);advance(&v->gain);
    if(v->rotation_ratio!=v->ratio.value)rotations(v);
    for(k=0;k<v->profile->count;++k) {
        double re=v->cosine[k],im=v->sine[k],next_re,next_im;
        for(c=0;c<2;++c)result[c]+=v->weight[k]*(v->re[k][c]*re-v->im[k][c]*im);
        next_re=re*v->dc[k]-im*v->ds[k];next_im=im*v->dc[k]+re*v->ds[k];
        if((v->frame&4095)==4095) {
            double norm=hypot(next_re,next_im);next_re/=norm;next_im/=norm;
        }
        v->cosine[k]=next_re;v->sine[k]=next_im;
    }
    out[0]=result[0]*v->gain.value;out[1]=result[1]*v->gain.value;++v->frame;return 1;
}
int ms_voice_process(MsVoice *v,double *out,unsigned frames) {
    unsigned n;
    if(!v||!v->profile||(frames&&!out))return 0;
    for(n=0;n<frames;++n)if(!ms_voice_tick(v,out+2*n))return 0;
    return 1;
}
