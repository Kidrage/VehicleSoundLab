#include "shape.h"
#include <math.h>
#include <string.h>
double drc_support(const DrcBank *b,unsigned a,double hz) {
    double x=hz/b->root[a],u;
    if(x<=b->outer_low||x>=b->outer_high)return 0;
    if(x<b->inner_low)u=(x-b->outer_low)/(b->inner_low-b->outer_low);
    else if(x>b->inner_high)u=(b->outer_high-x)/(b->outer_high-b->inner_high);
    else return 1;
    return u*u*(3-2*u);
}
void drc_weights(const DrcBank *b,double hz,double w[SA_MAX_ANCHORS]) {
    unsigned lo=0;double u;
    memset(w,0,SA_MAX_ANCHORS*sizeof *w);
    if(hz<=b->root[0]){w[0]=1;return;}
    if(hz>=b->root[b->count-1]){w[b->count-1]=1;return;}
    while(lo+1<b->count&&hz>b->root[lo+1])++lo;
    u=(hz-b->root[lo])/(b->root[lo+1]-b->root[lo]);w[lo]=1-u;w[lo+1]=u;
}
int drc_shape(const DrcBank *b,const SaVoice *dna,const DrsVoice *detail,double gain[SD_MAX_HARMONICS]) {
    unsigned a,h;double w[SA_MAX_ANCHORS],hz,amount=0;
    if(!b||!dna||!dna->bank||!gain||b->count!=dna->bank->count||
       !isfinite(dna->root_hz)||!isfinite(dna->root_target)||dna->root_hz<0||dna->root_hz>1000||
       dna->root_target<0||dna->root_target>1000)return 0;
    hz=dna->root_hz+dna->follow*(dna->root_target-dna->root_hz);drc_weights(b,hz,w);
    if(detail)amount=detail->amount+detail->follow*(detail->target-detail->amount);
    if(!isfinite(amount)||amount<0||amount>1)return 0;
    for(a=0;a<b->count;++a){double support=drc_support(b,a,hz);w[a]*=support*support*amount*amount;}
    for(h=0;h<dna->bank->harmonics;++h) {
        double power=0;for(a=0;a<b->count;++a)power+=w[a]*b->reduction[a][h];
        gain[h]=sqrt(fmax(0,1-power));
    }
    return 1;
}
