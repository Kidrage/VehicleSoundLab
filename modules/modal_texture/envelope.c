#include "envelope.h"
#include <math.h>
#include <string.h>
#define MT_PI 3.14159265358979323846
static int valid(double amount){return isfinite(amount)&&amount>=0&&amount<=1;}
/* Same declared Gaussian stream as the Python oracle; independent state,
   no coupling to the existing DNA/residual generators. */
static double uniform(MtEnvelope *s) {
    uint64_t x=s->rng;x^=x>>12;x^=x<<25;x^=x>>27;s->rng=x;
    return (((x*UINT64_C(2685821657736338717))>>11)+.5)/9007199254740992.;
}
static double gaussian(MtEnvelope *s) {
    double radius,angle;
    if(s->has_spare){s->has_spare=0;return s->spare;}
    radius=sqrt(-2*log(uniform(s)));angle=2*MT_PI*uniform(s);
    s->spare=radius*sin(angle);s->has_spare=1;return radius*cos(angle);
}
static void draw(MtEnvelope *s,double *out) {
    unsigned i,j;double normal[MT_MAX_MODES];
    for(j=0;j<s->profile->count;++j)normal[j]=gaussian(s);
    for(i=0;i<s->profile->count;++i) {
        double value=0;
        for(j=0;j<s->profile->count;++j)value+=s->profile->factor[i][j]*normal[j];
        out[i]=value;
    }
}
static void next(MtEnvelope *s) {
    unsigned i;double fresh[MT_MAX_MODES];draw(s,fresh);
    for(i=0;i<s->profile->count;++i)
        s->right[i]=s->profile->alpha*s->left[i]+s->innovation_scale*fresh[i];
}
int mt_envelope_init(MtEnvelope *out,const MtProfile *p,uint64_t seed,double amount) {
    MtEnvelope s;unsigned i,j;
    if(!out||!valid(amount)||!mt_profile_valid(p))return 0;
    memset(&s,0,sizeof s);s.profile=p;
    s.rng=seed^UINT64_C(0x8CB92BA72F3D8DD7);if(!s.rng)s.rng=1;
    s.amount=s.target=amount;s.innovation_scale=sqrt(1-p->alpha*p->alpha);
    for(i=0;i<p->count;++i)for(j=0;j<p->count;++j)s.variance[i]+=p->factor[i][j]*p->factor[i][j];
    draw(&s,s.left);next(&s);*out=s;return 1;
}
int mt_envelope_set(MtEnvelope *s,double amount) {
    if(!s||!s->profile||!valid(amount))return 0;
    if(amount!=s->target) {
        s->target=amount;s->remaining=MT_RAMP_FRAMES;s->step=(amount-s->amount)/MT_RAMP_FRAMES;
    }
    return 1;
}
int mt_envelope_tick(MtEnvelope *s,double *gain) {
    unsigned i;double u,v;
    if(!s||!s->profile||!gain)return 0;
    if(s->remaining){if(!--s->remaining)s->amount=s->target;else s->amount+=s->step;}
    u=.5-.5*cos(MT_PI*(double)s->position/s->profile->hop_frames);
    v=sqrt((1-u)*(1-u)+u*u+2*s->profile->alpha*u*(1-u));
    for(i=0;i<s->profile->count;++i) {
        double z=((1-u)*s->left[i]+u*s->right[i])/v;
        /* Gaussian marginal E[gain^2]=1. This is not finite-take loudness
           matching, nor a claim that windowed source magnitude is true AM. */
        gain[i]=exp(s->amount*z-s->amount*s->amount*s->variance[i]);
    }
    ++s->frame;
    if(++s->position==s->profile->hop_frames) {
        s->position=0;memcpy(s->left,s->right,sizeof s->left);next(s);
    }
    return 1;
}
