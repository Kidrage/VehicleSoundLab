#include "voice.h"
#include "resonant_detail/excitation.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
struct ScVoice {
    SfBank *bank[SC_STAGES];SfVoice *voice[SC_STAGES];
    double envelope[SC_POINTS],variation,gate,roughness,follow,release,rough_follow,rough_innovation;
    RdtExcitation rng;uint64_t frame;
    ScRidgeVoice ridges;
    CkVoice *rotation;
};
void sc_destroy(ScVoice *v){unsigned k;if(!v)return;for(k=0;k<SC_STAGES;++k){sf_voice_destroy(v->voice[k]);sf_bank_destroy(v->bank[k]);}free(v->rotation);free(v);}
int sc_set_rotation(ScVoice *v,const CkProfile *p,uint64_t seed){
    CkVoice *r;if(!v||v->frame||v->ridges.count||v->rotation)return 0;
    r=malloc(sizeof *r);if(!r)return 0;if(!ck_init(r,p,seed)){free(r);return 0;}v->rotation=r;return 1;
}
ScVoice *sc_create(const SfProfile *p[SC_STAGES],const double env[SC_POINTS],double variation,uint64_t seed){
    unsigned k;ScVoice *v;
    if(!p||!env||!seed||!isfinite(variation)||variation<0||variation>1)return NULL;
    for(k=0;k<SC_POINTS;++k)if(!isfinite(env[k])||env[k]<0||env[k]>4)return NULL;
    v=calloc(1,sizeof *v);if(!v)return NULL;
    memcpy(v->envelope,env,sizeof v->envelope);v->variation=variation;
    v->follow=1-exp(-1/(.008*48000));v->release=1-exp(-1/(.012*48000));
    v->rough_follow=1-exp(-1/(.012*48000));v->rough_innovation=sqrt(1-exp(-2/(.012*48000)));
    rdt_excitation_init(&v->rng,seed^UINT64_C(0xb7e151628aed2a6b));
    for(k=0;k<SC_STAGES;++k){
        v->bank[k]=sf_bank_create(p[k]);
        if(!v->bank[k]||!(v->voice[k]=sf_voice_create(v->bank[k],seed^(UINT64_C(0x9e3779b97f4a7c15)*(k+1))))){sc_destroy(v);return NULL;}
    }
    return v;
}
static double smooth(double x){return x*x*(3-2*x);}
int sc_set_ridges(ScVoice *v,const ScRidge *r,unsigned count,unsigned frames,double variation,double pitch,uint64_t seed){
    return v&&!v->frame&&!v->rotation?sc_ridge_init(&v->ridges,r,count,frames,variation,pitch,seed):0;
}
static int tick(ScVoice *v,double progress,int gate,double strength,double pitch,double cg,double tg,int expressive,double out[2]){
    double result[2]={0},core[2]={0},u,t,env,rough;unsigned k,c,index,stage;
    if(!v||!out||!isfinite(progress)||progress<0||progress>1||(gate!=0&&gate!=1)||
       !isfinite(strength)||strength<0||strength>4||!isfinite(pitch)||pitch<.5||pitch>2||
       !isfinite(cg)||cg<0||cg>3||!isfinite(tg)||tg<0||tg>3)return 0;
    u=progress*(SC_STAGES-1);stage=(unsigned)u;if(stage>=SC_STAGES-1)stage=SC_STAGES-2;
    t=smooth(u-stage);
    for(k=0;k<SC_STAGES;++k){
        double x[2],w=k==stage?sqrt(1-t):k==stage+1?sqrt(t):0;
        if(!sf_voice_tick(v->voice[k],x,NULL))return 0;
        for(c=0;c<2;++c)result[c]+=w*x[c];
    }
    u=progress*(SC_POINTS-1);index=(unsigned)u;if(index>=SC_POINTS-1)index=SC_POINTS-2;
    t=smooth(u-index);env=(1-t)*v->envelope[index]+t*v->envelope[index+1];
    /* Fresh bounded stochastic roughness, no recorded envelope/no periodic LFO.
       Innovation variance gives unit stationary variance before tanh bounding. */
    v->roughness+=v->rough_follow*(-v->roughness);
    v->roughness+=v->rough_innovation*rdt_excitation_next(&v->rng);
    rough=1+v->variation*tanh(v->roughness);
    v->gate+=(gate?v->follow:v->release)*(gate-v->gate);
    if(v->rotation){
        double air=1;
        if((gate||v->gate>1e-8)&&!ck_tick(v->rotation,progress,gate,pitch,1,core,&air))return 0;
        for(c=0;c<2;++c)out[c]=(result[c]*rough*tg*air+core[c]*cg)*env*v->gate*strength;
    }else if(v->ridges.count){
        if(expressive){if(!sc_ridge_tick_pitch(&v->ridges,progress,gate,pitch,core))return 0;}
        else sc_ridge_tick(&v->ridges,progress,gate,core);
        for(c=0;c<2;++c)out[c]=(result[c]*rough*tg+core[c]*cg)*env*v->gate*strength;
    }else for(c=0;c<2;++c)out[c]=result[c]*env*rough*v->gate*strength*tg;
    ++v->frame;return isfinite(out[0])&&isfinite(out[1]);
}
int sc_tick(ScVoice *v,double p,int gate,double strength,double out[2]){return tick(v,p,gate,strength,1,1,1,0,out);}
int sc_tick_expression(ScVoice *v,double p,int gate,double strength,double pitch,double cg,double tg,double out[2]){return tick(v,p,gate,strength,pitch,cg,tg,1,out);}
