#include "voice.h"
#include <math.h>
#include <string.h>
#define DRS_PI 3.14159265358979323846
static int unit(double x){return isfinite(x)&&x>=0&&x<=1;}
static double cycle(double x) {
    double phase=fmod(x,1);if(phase<0)phase+=1;
    /* A tiny negative remainder can round to1 when adding1. */
    return phase>=1?0:phase;
}
static double smooth(double x){return x*x*(3-2*x);}
static double support(const DrsBank *b,unsigned a,double hz) {
    double x=hz/b->root[a];
    if(x<=b->outer_low||x>=b->outer_high)return 0;
    if(x<b->inner_low)return smooth((x-b->outer_low)/(b->inner_low-b->outer_low));
    if(x>b->inner_high)return smooth((b->outer_high-x)/(b->outer_high-b->inner_high));
    return 1;
}
int drs_voice_init(DrsVoice *out,const DrsBank *b,const SaBank *dna,uint64_t seed,double amount) {
    DrsVoice v;unsigned a,n;
    if(!out||!unit(amount)||!drs_bank_valid(b,dna))return 0;
    memset(&v,0,sizeof v);v.bank=b;v.amount=v.target=amount;v.follow=1-exp(-1/(.018*48000));
    for(a=0;a<b->count;++a)if(b->enabled[a]) {
        if(b->kind[a]==DRS_STEREO) {
            if(!rvs_voice_init(v.stereo+a,b->stereo+a,seed^(UINT64_C(0x9e3779b97f4a7c15)*a),1))return 0;
            continue;
        }
        const RdtProfile *p=b->profile+a;double unused[2];
        if(!rdt_voice_init(v.voice+a,p,seed^(UINT64_C(0x9e3779b97f4a7c15)*a)))return 0;
        for(n=0;n<p->warmup_frames;++n) {
            double phase=cycle(((double)n-p->warmup_frames)*p->base_hz/48000+dna->offset[a]/(2*DRS_PI));
            if(!rdt_voice_tick(v.voice+a,phase,unused,NULL))return 0;
        }
    }*out=v;return 1;
}
int drs_voice_set(DrsVoice *v,double amount){if(!v||!v->bank||!unit(amount))return 0;v->target=amount;return 1;}
int drs_voice_tick(DrsVoice *v,const SaVoice *dna,double sampled_phase,DrsFrame *f) {
    unsigned a,c;const DrsBank *b;
    if(!v||!v->bank||!dna||!dna->bank||!f||!isfinite(sampled_phase)||sampled_phase<0||sampled_phase>=2*DRS_PI||
       dna->bank->count!=v->bank->count||dna->lower>=v->bank->count||dna->upper>=v->bank->count||!unit(dna->blend))return 0;
    b=v->bank;memset(f,0,sizeof *f);
    for(a=0;a<b->count;++a)if(b->enabled[a]) {
        double x[2],weight=0,phase=cycle((sampled_phase+dna->bank->offset[a])/(2*DRS_PI));
        if(b->kind[a]==DRS_STEREO) {if(!rvs_voice_tick(v->stereo+a,x,NULL))return 0;}
        else if(!rdt_voice_tick(v->voice+a,phase,x,NULL))return 0;
        if(dna->lower==dna->upper){if(a==dna->lower)weight=1;}
        else if(a==dna->lower)weight=1-dna->blend;else if(a==dna->upper)weight=dna->blend;
        weight=sqrt(weight)*support(b,a,dna->root_hz);f->support+=weight*weight;
        for(c=0;c<2;++c)f->raw[c]+=x[c]*weight;
    }
    v->amount+=v->follow*(v->target-v->amount);
    for(c=0;c<2;++c)f->output[c]=f->raw[c]*v->amount;++v->frame;return 1;
}
