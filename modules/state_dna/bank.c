#include "lookup.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
static double wrap(double x){return remainder(x,2*PI);}
static double score(const SaBank *base,const SaBank *donor,unsigned orders,double offset) {
    unsigned a,h,c;double sum=0;
    for(a=0;a<donor->count;++a)for(h=0;h<orders;++h)for(c=0;c<2;++c) {
        unsigned lo,hi;double t,ma,mb;const double *z=donor->profile[a]->harmonic[h].mean;
        sx_position(base,donor->profile[a]->base_hz,&lo,&hi,&t);
        const double *x=base->profile[lo]->harmonic[h].mean;
        ma=hypot(x[2*c],x[2*c+1]);
        if(lo!=hi){x=base->profile[hi]->harmonic[h].mean;ma+=t*(hypot(x[2*c],x[2*c+1])-ma);}
        mb=hypot(z[2*c],z[2*c+1]);
        sum+=ma*mb*cos(sx_phase(base,donor->profile[a]->base_hz,h,c)-donor->phase[a][h][c]-(h+1)*offset);
    }
    return sum;
}
static double origin(const SaBank *base,const SaBank *donor,unsigned orders) {
    unsigned i,pass;double best=0,step=2*PI/4096,value=score(base,donor,orders,0);
    if(!orders)return 0;
    for(i=0;i<4096;++i){double x=-PI+i*step,v=score(base,donor,orders,x);
        if(v>value+1e-15||(fabs(v-value)<=1e-15&&fabs(x)<fabs(best))){best=x;value=v;}}
    for(pass=0;pass<3;++pass){double center=best;step/=16;
        for(i=0;i<=32;++i){double x=center+((int)i-16)*step,v=score(base,donor,orders,x);
            if(v>value){best=x;value=v;}}}
    return wrap(best);
}
static void insert(SxBank *b,unsigned s,double root) {
    unsigned i=0,j;while(i<b->nodes[s]&&b->root[s][i]<root)++i;
    if(i<b->nodes[s]&&fabs(b->root[s][i]-root)<1e-9)return;
    for(j=b->nodes[s];j>i;--j)b->root[s][j]=b->root[s][j-1];
    b->root[s][i]=root;++b->nodes[s];
}
int sx_bank_init(SxBank *b,const SaBank *base,const SaBank *const *donors,unsigned orders,double seconds) {
    unsigned s,a,h;
    if(!b||!base||!donors||!base->count||base->count>SA_MAX_ANCHORS||orders>32||
       !isfinite(seconds)||seconds<.02||seconds>2.6)return 0;
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
            double root=b->root[s][a],bl=sx_phase(base,root,h,0),br=sx_phase(base,root,h,1);
            double dl=sx_phase(d,root,h,0),dr=sx_phase(d,root,h,1);
            double left=wrap(dl+(h+1)*b->origin[s]-bl),relative=wrap((dr-dl)-(br-bl));
            if(a){double previous=b->delta[s][a-1][h][0];left=previous+wrap(left-previous);
                previous=b->delta[s][a-1][h][1]-previous;relative=previous+wrap(relative-previous);}
            b->delta[s][a][h][0]=left;b->delta[s][a][h][1]=left+relative;
        }
    }
    return 1;
}
