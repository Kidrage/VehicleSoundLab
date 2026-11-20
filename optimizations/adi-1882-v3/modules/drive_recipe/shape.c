#include "dsp/perf.h"
#include "shape.h"
#include <math.h>
#include <string.h>
float drc_support(const DrcBank *b,unsigned a,float hz) {
    float x=hz/b->root[a],u;
    if(x<=b->outer_low||x>=b->outer_high)return 0;
    if(x<b->inner_low)u=(x-b->outer_low)/(b->inner_low-b->outer_low);
    else if(x>b->inner_high)u=(b->outer_high-x)/(b->outer_high-b->inner_high);
    else return 1;
    return u*u*(3-2*u);
}
void drc_weights(const DrcBank *b,float hz,float w[SA_MAX_ANCHORS]) {
    unsigned lo=0;float u;
    memset(w,0,SA_MAX_ANCHORS*sizeof *w);
    if(hz<=b->root[0]){w[0]=1;return;}
    if(hz>=b->root[b->count-1]){w[b->count-1]=1;return;}
    while(lo+1<b->count&&hz>b->root[lo+1])++lo;
    u=(hz-b->root[lo])/(b->root[lo+1]-b->root[lo]);w[lo]=1-u;w[lo+1]=u;
}
int drc_shape(const DrcBank *b,const SaVoice *dna,const DrsVoice *detail,float gain[SD_MAX_HARMONICS]);
int drc_shape_impl(const DrcBank *b,const SaVoice *dna,const DrsVoice *detail,float gain[SD_MAX_HARMONICS]){
    unsigned a,h;int active=0;float w[SA_MAX_ANCHORS],hz,amount=0;
    if(!b||!dna||!dna->bank||!gain||b->count!=dna->bank->count||
       !isfinite(dna->root_hz)||!isfinite(dna->root_target)||dna->root_hz<0||dna->root_hz>1000||
       dna->root_target<0||dna->root_target>1000)return 0;
    hz=dna->root_hz+dna->follow*(dna->root_target-dna->root_hz);drc_weights(b,hz,w);
    if(detail)amount=detail->amount+detail->follow*(detail->target-detail->amount);
    if(!isfinite(amount)||amount<0||amount>1.3f)return 0;
    for(a=0;a<b->count;++a){float support=drc_support(b,a,hz);w[a]*=support*support*amount*amount;if(w[a]!=0)active=1;}
    /* A validated bank has finite nonnegative reductions. When every weight
       is zero the original ordered power sum is exactly zero for every order. */
    if(!active){for(h=0;h<dna->bank->harmonics;++h)gain[h]=1;return 1;}
    for(h=0;h<dna->bank->harmonics;++h) {
        float power=0;for(a=0;a<b->count;++a)power+=w[a]*b->reduction[a][h];
        /* sqrt(1) is exactly one. Unsupported anchors have zero power, often
           across the whole bank; retain the original path for all other values. */
        gain[h]=power==0?1:sqrtf(fmaxf(0,1-power));
    }
    return 1;
}
int drc_shape(const DrcBank *b,const SaVoice *dna,const DrsVoice *detail,float gain[SD_MAX_HARMONICS]){vsl_perf_enter(2);int result=drc_shape_impl(b,dna,detail,gain);vsl_perf_leave();return result;}

