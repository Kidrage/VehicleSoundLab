#include "recipe.h"
#include <math.h>
static int bounded(double v,double bound) {return isfinite(v)&&fabs(v)<=bound;}
int rss_profile_valid(const SdProfile *m) {
    unsigned h,k,c,j;
    if(!m||m->rate!=48000||m->window!=1024||m->hop!=256||!m->harmonics||
       m->harmonics>SD_MAX_HARMONICS||m->components>SD_MAX_COMPONENTS||
       !isfinite(m->base_hz)||m->base_hz<5||m->base_hz>2000||
       m->harmonics*m->base_hz*1.1>.45*m->rate)return 0;
    for(k=0;k<m->components;++k)if(!bounded(m->rho[k],.95))return 0;
    for(h=0;h<m->harmonics;++h) {
        const SdHarmonic *a=m->harmonic+h;
        if(!bounded(a->rho,.95))return 0;
        for(c=0;c<4;++c) {
            if(!bounded(a->mean[c],4))return 0;
            for(k=0;k<m->components;++k)if(!bounded(a->basis[k][c],4))return 0;
            for(j=0;j<4;++j)if(!bounded(a->root[c][j],4))return 0;
        }
    }
    return 1;
}
int rss_profile_prepare(SdProfile *out,const SdProfile *m,const RssColour *p) {
    unsigned h,k,c,j;
    if(!out||out==m||!rss_profile_valid(m)||!p||!isfinite(p->power_reduction)||
       p->power_reduction<0||p->power_reduction>=1||!isfinite(p->low_hz)||
       !isfinite(p->high_hz)||p->low_hz<20||p->high_hz<=p->low_hz||p->high_hz>21600)return 0;
    *out=*m;
    if(p->power_reduction==0)return 1;
    for(h=0;h<m->harmonics;++h) {
        double u=((h+1)*m->base_hz-p->low_hz)/(p->high_hz-p->low_hz),gain;
        SdHarmonic *a=out->harmonic+h;
        if(u<=0)continue;
        if(u>1)u=1;
        u=u*u*(3-2*u);
        gain=sqrt(1-p->power_reduction*u);
        for(c=0;c<4;++c) {
            a->mean[c]*=gain;
            for(k=0;k<m->components;++k)a->basis[k][c]*=gain;
            for(j=0;j<4;++j)a->root[c][j]*=gain;
        }
    }
    return 1;
}
