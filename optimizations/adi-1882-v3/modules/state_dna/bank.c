#include "lookup.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
static float wrap(float x){return remainderf(x,2*PI);}
static float score(const SaBank *base,const SaBank *donor,unsigned orders,float offset) {
    unsigned a,h,c;float sum=0;
    for(a=0;a<donor->count;++a)for(h=0;h<orders;++h)for(c=0;c<2;++c) {
        unsigned lo,hi;float t,ma,mb;const float *z=donor->profile[a]->harmonic[h].mean;
        sx_position(base,donor->profile[a]->base_hz,&lo,&hi,&t);
        const float *x=base->profile[lo]->harmonic[h].mean;
        ma=hypotf(x[2*c],x[2*c+1]);
        if(lo!=hi){x=base->profile[hi]->harmonic[h].mean;ma+=t*(hypotf(x[2*c],x[2*c+1])-ma);}
        mb=hypotf(z[2*c],z[2*c+1]);
        sum+=ma*mb*cosf(sx_phase(base,donor->profile[a]->base_hz,h,c)-donor->phase[a][h][c]-(h+1)*offset);
    }
    return sum;
}
static float origin(const SaBank *base,const SaBank *donor,unsigned orders) {
    unsigned i,pass;float best=0,step=2*PI/4096,value=score(base,donor,orders,0);
    if(!orders)return 0;
    for(i=0;i<4096;++i){float x=-PI+i*step,v=score(base,donor,orders,x);
        if(v>value+1e-15f||(fabsf(v-value)<=1e-15f&&fabsf(x)<fabsf(best))){best=x;value=v;}}
    for(pass=0;pass<3;++pass){float center=best;step/=16;
        for(i=0;i<=32;++i){float x=center+((int)i-16)*step,v=score(base,donor,orders,x);
            if(v>value){best=x;value=v;}}}
    return wrap(best);
}
static void insert(SxBank *b,unsigned s,float root) {
    unsigned i=0,j;while(i<b->nodes[s]&&b->root[s][i]<root)++i;
    if(i<b->nodes[s]&&fabsf(b->root[s][i]-root)<1e-9f)return;
    for(j=b->nodes[s];j>i;--j)b->root[s][j]=b->root[s][j-1];
    b->root[s][i]=root;++b->nodes[s];
}
int sx_bank_init(SxBank *b,const SaBank *base,const SaBank *const *donors,unsigned orders,float seconds) {
    unsigned s,a,h;
    if(!b||!base||!donors||!base->count||base->count>SA_MAX_ANCHORS||orders>32||
       !isfinite(seconds)||seconds<.02f||seconds>2.6f)return 0;
    for(s=0;s<SX_STATES-1;++s)if(donors[s]&&(!donors[s]->count||donors[s]->count>SA_MAX_ANCHORS||
        donors[s]->harmonics!=base->harmonics))return 0;
    memset(b,0,sizeof *b);b->base=base;b->transition_seconds=seconds;b->mask=1;
    if(orders>base->harmonics)orders=base->harmonics;
    for(s=0;s<SX_STATES-1;++s)if(donors[s]) {
        const SaBank *d=donors[s];b->donor[s]=d;b->mask|=1u<<(s+1);
        b->origin[s]=origin(base,d,orders);
        for(a=0;a<base->count;++a)insert(b,s,base->profile[a]->base_hz);
        for(a=0;a<d->count;++a)insert(b,s,d->profile[a]->base_hz);
        for(h=0;h<base->harmonics;++h)for(a=0;a<b->nodes[s];++a) {
            float root=b->root[s][a],bl=sx_phase(base,root,h,0),br=sx_phase(base,root,h,1);
            float dl=sx_phase(d,root,h,0),dr=sx_phase(d,root,h,1);
            float left=wrap(dl+(h+1)*b->origin[s]-bl),relative=wrap((dr-dl)-(br-bl));
            if(a){float previous=b->delta[s][a-1][h][0];left=previous+wrap(left-previous);
                previous=b->delta[s][a-1][h][1]-previous;relative=previous+wrap(relative-previous);}
            b->delta[s][a][h][0]=left;b->delta[s][a][h][1]=left+relative;
        }
    }
    return 1;
}
