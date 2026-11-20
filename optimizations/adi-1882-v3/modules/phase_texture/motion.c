#include "motion.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
static float uniform(PtMotion *s) {
    uint64_t x=s->rng; x^=x>>12; x^=x<<25; x^=x>>27; s->rng=x;
    return (((x*UINT64_C(2685821657736338717))>>11)+.5f)/9007199254740992.f;
}
static float gaussian(PtMotion *s) {
    float r,a;
    if(s->has_spare) {s->has_spare=0;return s->spare;}
    r=sqrtf(-2*logf(uniform(s)));a=2*PI*uniform(s);
    s->spare=r*sinf(a);s->has_spare=1;return r*cosf(a);
}
static float node(PtMotion *s) {
    static const float sos[2][5]={
        {.3242446420921886f,.6484892841843772f,.3242446420921886f,.8905909629401298f,.39145561239824345f},
        {1,-2,1,-1.0667509721405004f,.44510115026522284f}};
    float x=gaussian(s);unsigned i;
    for(i=0;i<2;++i) {
        float y=sos[i][0]*x+s->filter[i][0];
        s->filter[i][0]=sos[i][1]*x-sos[i][3]*y+s->filter[i][1];
        s->filter[i][1]=sos[i][2]*x-sos[i][4]*y;x=y;
    }
    /* Fixed impulse-response variance; never per-render loudness matching. */
    return x/sqrtf(.5306853062531296f);
}
static void spline(PtMotion *s) {
    float upper[PT_NODES];unsigned i,n=s->count;
    s->second[0]=upper[0]=0;
    for(i=1;i+1<n;++i) {
        float divisor=4-upper[i-1];
        upper[i]=1/divisor;
        s->second[i]=(6*(s->nodes[i+1]-2*s->nodes[i]+s->nodes[i-1])-s->second[i-1])/divisor;
    }
    s->second[n-1]=0;
    for(i=n-2;i>0;--i)s->second[i]-=upper[i]*s->second[i+1];
    for(i=0;i<PT_SPAN;++i) {
        unsigned j=s->first+i;
        float *c=s->cubic[i],a=s->second[j],b=s->second[j+1];
        c[0]=s->nodes[j];c[1]=s->nodes[j+1]-s->nodes[j]-(2*a+b)/6;
        c[2]=a/2;c[3]=(b-a)/6;
    }
}
static void refill(PtMotion *s) {
    unsigned start=s->first+PT_SPAN-PT_MARGIN,keep=s->count-start,i;
    memmove(s->nodes,s->nodes+start,keep*sizeof(float));
    s->first=PT_MARGIN;s->count=PT_NODES;
    for(i=keep;i<s->count;++i)s->nodes[i]=node(s);
    spline(s);s->interval=0;
}
void pt_motion_init(PtMotion *s,uint64_t seed) {
    unsigned i;memset(s,0,sizeof *s);s->rng=seed?seed:1;
    for(i=0;i<2048;++i)(void)node(s);
    s->count=PT_SPAN+PT_MARGIN+1;
    for(i=0;i<s->count;++i)s->nodes[i]=node(s);
    spline(s);
}
float pt_motion_tick(PtMotion *s) {
    float u,x,*c;
    if(s->interval==PT_SPAN)refill(s);
    c=s->cubic[s->interval];u=s->sample/256.f;
    x=((c[3]*u+c[2])*u+c[1])*u+c[0];
    if(++s->sample==256) {s->sample=0;++s->interval;}
    ++s->frame;
    s->last_seconds=4e-6f*tanhf(x/2);
    return s->last_seconds;
}
