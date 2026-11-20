#include "voice.h"
#include <math.h>
/* Recursive rotations need the original coefficients: a small phase error
   would accumulate for every following sample. */
#ifdef VSL_DSP_FAST_TRIG
#undef sinf
#undef cosf
#endif
#include <float.h>
#include <string.h>
#define MS_PI 3.14159265358979323846f
static int valid(float r,float g){return isfinite(r)&&r>=.25f&&r<=4&&isfinite(g)&&g>=0&&g<=1;}
static float taper(float hz) {
    float x;
    if(hz<=19200)return 1;
    if(hz>=21600)return 0;
    x=(hz-19200)/2400;return 1-x*x*(3-2*x);
}
static void rotations(MsVoice *v) {
    unsigned k;
    for(k=0;k<v->profile->count;++k) {
        float hz=v->profile->mode[k].hz*v->ratio.value;
        float angle=2*MS_PI*fmodf(hz/MS_RATE,1);
        v->dc[k]=cosf(angle);v->ds[k]=sinf(angle);v->weight[k]=taper(hz);
    }
    v->rotation_ratio=v->ratio.value;
}
static void track_rotations(MsVoice *v) {
    unsigned k;float step=v->ratio.step;
    if(v->rotation_ratio==v->ratio.value)return;
    if(!v->ratio.left||v->rotation_step!=step||!(v->frame&63)) {
        rotations(v);
        if(v->ratio.left&&v->rotation_step!=step) {
            for(k=0;k<v->profile->count;++k){
                float a=2*MS_PI*v->profile->mode[k].hz/MS_RATE*step;
                v->step_dc[k]=cosf(a);v->step_ds[k]=sinf(a);
            }
            v->rotation_step=step;
        }
    }else {
        for(k=0;k<v->profile->count;++k) {
            float dc=v->dc[k],ds=v->ds[k];
            v->dc[k]=dc*v->step_dc[k]-ds*v->step_ds[k];
            v->ds[k]=ds*v->step_dc[k]+dc*v->step_ds[k];
            v->weight[k]=taper(v->profile->mode[k].hz*v->ratio.value);
        }
        v->rotation_ratio=v->ratio.value;
    }
}
static void adopt(MsRamp *r,float target) {
    if(target==r->target)return;
    r->target=target;r->left=MS_RAMP_FRAMES;r->step=(target-r->value)/MS_RAMP_FRAMES;
}
static void advance(MsRamp *r) {
    if(r->left){if(!--r->left)r->value=r->target;else r->value+=r->step;}
}
int ms_voice_init(MsVoice *out,const MsProfile *p,float ratio,float gain) {
    MsVoice v;unsigned k,c;
    if(!out||!valid(ratio,gain)||!ms_profile_valid(p))return 0;
    memset(&v,0,sizeof v);v.profile=p;
    v.ratio.value=v.ratio.target=ratio;v.gain.value=v.gain.target=gain;
    for(k=0;k<p->count;++k) {
        v.cosine[k]=1;
        for(c=0;c<2;++c) {
            float phase=remainderf(p->mode[k].phase[c],2*MS_PI);
            v.re[k][c]=p->mode[k].amplitude[c]*cosf(phase);
            v.im[k][c]=p->mode[k].amplitude[c]*sinf(phase);
        }
    }
    rotations(&v);*out=v;return 1;
}
int ms_voice_set(MsVoice *v,float ratio,float gain) {
    if(!v||!v->profile||!valid(ratio,gain))return 0;
    adopt(&v->ratio,ratio);adopt(&v->gain,gain);return 1;
}
int ms_voice_tick_gains(MsVoice *v,const float *gains,float out[2]) {
    unsigned k,c;float result[2]={0,0};
    if(!v||!v->profile||!out)return 0;
    if(gains)for(k=0;k<v->profile->count;++k)
        if(!isfinite(gains[k])||gains[k]<0||gains[k]>FLT_MAX/64)return 0;
    advance(&v->ratio);advance(&v->gain);
    track_rotations(v);
    for(k=0;k<v->profile->count;++k) {
        float re=v->cosine[k],im=v->sine[k],next_re,next_im;
        for(c=0;c<2;++c) {
            float contribution=v->weight[k]*(v->re[k][c]*re-v->im[k][c]*im);
            if(gains)contribution*=gains[k];
            result[c]+=contribution;
        }
        next_re=re*v->dc[k]-im*v->ds[k];next_im=im*v->dc[k]+re*v->ds[k];
        if((v->frame&4095)==4095) {
            float norm=hypotf(next_re,next_im);next_re/=norm;next_im/=norm;
        }
        v->cosine[k]=next_re;v->sine[k]=next_im;
    }
    out[0]=result[0]*v->gain.value;out[1]=result[1]*v->gain.value;++v->frame;return 1;
}
int ms_voice_tick(MsVoice *v,float out[2]) {return ms_voice_tick_gains(v,NULL,out);}
int ms_voice_process(MsVoice *v,float *out,unsigned frames) {
    unsigned n;
    if(!v||!v->profile||(frames&&!out))return 0;
    for(n=0;n<frames;++n)if(!ms_voice_tick(v,out+2*n))return 0;
    return 1;
}
