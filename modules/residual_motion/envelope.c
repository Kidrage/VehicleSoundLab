#include "envelope.h"
#include <math.h>
#include <string.h>
static double sign(uint64_t *seed) {
    uint64_t z=(*seed+=UINT64_C(0x9e3779b97f4a7c15));
    z=(z^(z>>30))*UINT64_C(0xbf58476d1ce4e5b9);z=(z^(z>>27))*UINT64_C(0x94d049bb133111eb);
    return ((z^(z>>31))>>63)?1.:-1.;
}
static int valid(double amount){return isfinite(amount)&&amount>=0&&amount<=1;}
static double next(RmEnvelope *s,unsigned k,double previous) {
    return s->profile.rho[k]*previous+s->innovation[k]*sign(&s->seed);
}
int rm_envelope_init(RmEnvelope *s,const RmProfile *p,uint64_t seed,double amount) {
    unsigned k,i;if(!s||!rm_profile_valid(p)||!valid(amount))return 0;
    memset(s,0,sizeof *s);s->profile=*p;s->seed=seed;s->amount=s->target=amount;
    s->follow=1-exp(-1/(.018*48000));
    for(k=0;k<p->factors;++k) {
        s->innovation[k]=sqrt(1-p->rho[k]*p->rho[k]);
        for(i=0;i<4096;++i)s->left[k]=next(s,k,s->left[k]);
        s->right[k]=next(s,k,s->left[k]);
    }
    s->initialized=1;return 1;
}
int rm_envelope_set(RmEnvelope *s,double amount) {
    if(!s||!s->initialized||!valid(amount))return 0;s->target=amount;return 1;
}
void rm_envelope_tick(RmEnvelope *s,double gain[SR_MAX_BANDS]) {
    unsigned k,b;double fraction=(s->frame%480)/480.;
    double variance[RM_MAX_FACTORS],value[RM_MAX_FACTORS];
    s->amount+=s->follow*(s->target-s->amount);
    for(k=0;k<s->profile.factors;++k) {
        value[k]=s->left[k]+fraction*(s->right[k]-s->left[k]);
        variance[k]=(1-fraction)*(1-fraction)+fraction*fraction+
                    2*s->profile.rho[k]*fraction*(1-fraction);
    }
    for(b=0;b<s->profile.bands;++b) {
        double deviation=0,power=0;
        for(k=0;k<s->profile.factors;++k) {
            double coefficient=s->profile.basis[b][k];
            deviation+=coefficient*value[k];power+=coefficient*coefficient*variance[k];
        }
        /* Interpolation variance is included at the actual amount. Expected
           gain^2 remains1; the RNG and carriers never depend on this amount. */
        gain[b]=(1+s->amount*deviation)/sqrt(1+s->amount*s->amount*power);
    }
    ++s->frame;
    if(s->frame%480==0)for(k=0;k<s->profile.factors;++k) {
        s->left[k]=s->right[k];s->right[k]=next(s,k,s->left[k]);
    }
}
