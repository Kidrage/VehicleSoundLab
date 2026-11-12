#include "profile.h"
#include "envelope.h"
#include <math.h>
/* Step-down Schur recursion on a(z/r), not a supplied pole-radius claim. */
static int stable(const double *a,unsigned n) {
    double x[RDT_MAX_AR+1],next[RDT_MAX_AR+1],scale=1;
    unsigned i,m;
    if(n>RDT_MAX_AR||a[0]!=1)return 0;
    x[0]=1;
    for(i=1;i<=n;++i) {
        scale*=.9998;
        if(!isfinite(a[i])||fabs(a[i])>32)return 0;
        x[i]=a[i]/scale;
    }
    for(m=n;m>0;--m) {
        double k=x[m],den=1-k*k;
        if(!isfinite(k)||fabs(k)>=1)return 0;
        next[0]=1;
        for(i=1;i<m;++i)next[i]=(x[i]-k*x[m-i])/den;
        for(i=0;i<m;++i)x[i]=next[i];
    }
    return 1;
}
int rdt_profile_valid(const RdtProfile *p) {
    unsigned b,s,j;
    if(!p||p->rate!=48000||!p->count||p->count>RDT_MAX_BANDS||p->warmup_frames>480000||
       !isfinite(p->base_hz)||p->base_hz<5||p->base_hz>1000)return 0;
    for(b=0;b<p->count;++b) {
        const RdtBand *m=p->band+b;
        if(!isfinite(m->low_hz)||!isfinite(m->high_hz)||m->low_hz<20||
           m->high_hz<=m->low_hz||m->high_hz>21600||!m->order||m->order>RDT_MAX_AR||
           !m->sections||m->sections>RDT_MAX_SOS||m->envelope_order>RDT_MAX_ENVELOPE||
           !isfinite(m->sigma)||m->sigma<=0||m->sigma>100||
           !isfinite(m->gain)||m->gain<0||m->gain>4||
           !isfinite(m->right_over_left)||m->right_over_left<0||m->right_over_left>4||
           !stable(m->a,m->order)||!rdt_envelope_valid(m))return 0;
        for(s=0;s<m->sections;++s) {
            for(j=0;j<6;++j)if(!isfinite(m->sos[s][j])||fabs(m->sos[s][j])>32)return 0;
            if(!stable(m->sos[s]+3,2))return 0;
        }
    }
    return 1;
}
