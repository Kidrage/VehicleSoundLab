#include "voice.h"
#include <math.h>
#include <string.h>
static int valid(double root,double gain) {return isfinite(root)&&root>=0&&root<=1000&&isfinite(gain)&&gain>=0&&gain<=1;}
static void select_anchor(RaVoice *v) {
    const RaBank *b=v->bank;unsigned lo=0,hi=0;double t=0;
    v->coverage=v->root<b->root[0]-1e-8?-1:v->root>b->root[b->count-1]+1e-8?1:0;
    if(v->root>=b->root[b->count-1])lo=hi=b->count-1;
    else if(v->root>b->root[0]) {
        while(lo+1<b->count&&v->root>b->root[lo+1])++lo;
        hi=lo+1;t=(v->root-b->root[lo])/(b->root[hi]-b->root[lo]);
    }
    v->lower=lo;v->upper=hi;v->blend=t;
}
static void matrix(const SrBand *p,double out[4]) {
    double norm=sqrt(p->power[0]*p->power[1]);
    out[0]=p->power[0];out[1]=p->power[1];out[2]=p->coherence[0]*norm;out[3]=p->coherence[1]*norm;
}
int ra_voice_init(RaVoice *v,const RaBank *bank,uint64_t seed,double root,double gain) {
    unsigned b;
    if(!v||!ra_bank_valid(bank)||!valid(root,gain))return 0;
    memset(v,0,sizeof *v);v->bank=bank;v->root=v->root_target=root;v->gain=v->gain_target=gain;
    v->follow=1-exp(-1/(.018*48000));select_anchor(v);
    sr_cloud_init(&v->cloud,&bank->profile[0],seed);sr_cloud_tune(&v->cloud,1);
    for(b=0;b<bank->profile[0].bands;++b) {
        double a[4],z[4];unsigned c;
        matrix(&bank->profile[v->lower].band[b],a);matrix(&bank->profile[v->upper].band[b],z);
        for(c=0;c<4;++c)v->covariance[b][c]=a[c]+v->blend*(z[c]-a[c]);
    }
    return 1;
}
int ra_voice_set(RaVoice *v,double root,double gain) {
    if(!v||!v->bank||!valid(root,gain))return 0;
    v->root_target=root;v->gain_target=gain;return 1;
}
void ra_voice_tick(RaVoice *v,double out[2],double raw[2]) {
    const RaBank *bank=v->bank;unsigned b,c;double samples[SR_MAX_BANDS][3],result[2]={0};
    v->root+=v->follow*(v->root_target-v->root);v->gain+=v->follow*(v->gain_target-v->gain);select_anchor(v);
    sr_cloud_observe(&v->cloud,bank->profile[0].bands,bank->profile[0].partials,samples,v->frame%1024==0);
    for(b=0;b<bank->profile[0].bands;++b) {
        double a[4],z[4],*p=v->covariance[b],left,shared_re=0,shared_im=0,independent;
        matrix(&bank->profile[v->lower].band[b],a);matrix(&bank->profile[v->upper].band[b],z);
        /* Convex covariance interpolation/following preserves positive
           semidefiniteness, unlike interpolating complex correlation alone. */
        for(c=0;c<4;++c)p[c]+=v->follow*(a[c]+v->blend*(z[c]-a[c])-p[c]);
        left=sqrt(fmax(0,p[0]));
        if(left>1e-15){shared_re=p[2]/left;shared_im=p[3]/left;}
        independent=sqrt(fmax(0,p[1]-shared_re*shared_re-shared_im*shared_im));
        if(p[0]==p[1]&&p[2]==p[0]&&p[3]==0){shared_re=left;shared_im=0;independent=0;}
        result[0]+=left*samples[b][0];
        result[1]+=shared_re*samples[b][0]-shared_im*samples[b][1]+independent*samples[b][2];
    }
    if(raw){raw[0]=result[0];raw[1]=result[1];}
    out[0]=result[0]*v->gain;out[1]=result[1]*v->gain;++v->frame;
}
