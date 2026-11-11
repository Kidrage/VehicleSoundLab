#include "cloud.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
#define HOP 192
static double uniform(LrCloud *s){uint64_t x=s->rng;x^=x>>12;x^=x<<25;x^=x>>27;s->rng=x;
    return (((x*UINT64_C(2685821657736338717))>>11)+.5)/9007199254740992.;}
static double normal(LrCloud *s){double r,a;if(s->has_spare){s->has_spare=0;return s->spare;}
    r=sqrt(-2*log(uniform(s)));a=2*PI*uniform(s);s->spare=r*sin(a);s->has_spare=1;return r*cos(a);}
static void advance(LrCloud *s,const LrProfile *m){unsigned i,c;
    for(i=0;i<m->count;++i)for(c=0;c<2;++c){s->left[i][c]=s->right[i][c];s->right[i][c]=s->rho*s->left[i][c]+s->innovation*normal(s);}}
void lr_cloud_init(LrCloud *s,const LrProfile *m,uint64_t seed){unsigned i,c;memset(s,0,sizeof *s);s->rng=seed?seed:1;
    s->rho=exp(-HOP/(m->rate*m->tau));s->innovation=sqrt(1-s->rho*s->rho);
    for(i=0;i<m->count;++i)for(c=0;c<2;++c)s->right[i][c]=normal(s);advance(s,m);
}
double lr_cloud_sample(LrCloud *s,const LrProfile *m,double pitch){
    unsigned i;double t,u,v,norm,cl,sl,dc,ds,out=0;
    if(s->position==HOP){s->position=0;advance(s,m);}
    t=s->position/(double)HOP;v=t*t*(3-2*t);u=1-v;
    norm=1/sqrt(u*u+v*v+2*s->rho*u*v);
    cl=cos(s->phase_first);sl=sin(s->phase_first);dc=cos(s->phase_step);ds=sin(s->phase_step);
    for(i=0;i<m->count;++i){double re=(u*s->left[i][0]+v*s->right[i][0])*norm,im=(u*s->left[i][1]+v*s->right[i][1])*norm,next;
        out+=m->amplitude[i]*(re*cl-im*sl);next=sl*dc+cl*ds;cl=cl*dc-sl*ds;sl=next;}
    s->phase_first+=2*PI*m->first_hz*pitch/m->rate;if(s->phase_first>=2*PI)s->phase_first-=2*PI;
    s->phase_step+=2*PI*m->step_hz*pitch/m->rate;if(s->phase_step>=2*PI)s->phase_step-=2*PI;
    ++s->position;++s->frame;return out;
}
