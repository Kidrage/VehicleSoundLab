#include "envelope.h"
#include <math.h>
#include <string.h>
#define MT_PI 3.14159265358979323846f
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
/* The modal fingerprint's amplitude motion is much slower than audio.
   Evaluate the unchanged formula at endpoints at most 32 samples apart,
   interpolate positive gains, and keep all original state/RNG ticks.
   Future endpoints stop at the current noise hop; no future draw is consumed.
   One serialized cache; switching owners safely rebuilds its endpoints. */
static const MtEnvelope *mt_cache_owner;
static uint64_t mt_cache_frame;
static unsigned mt_cache_begin,mt_cache_end;
static float mt_cache_target,mt_gain_begin[MT_MAX_MODES],mt_gain_end[MT_MAX_MODES];
static void mt_gains_at(const MtEnvelope *s,unsigned position,float amount,float *out){
    unsigned i;float u=.5f-.5f*cosf(MT_PI*(float)position/s->profile->hop_frames);
    float v=sqrtf((1-u)*(1-u)+u*u+2*s->profile->alpha*u*(1-u));
    for(i=0;i<s->profile->count;++i){
        float z=((1-u)*s->left[i]+u*s->right[i])/v;
        out[i]=expf(amount*z-amount*amount*s->variance[i]);
    }
}
static void mt_gains_cached(const MtEnvelope *s,float *out){
    unsigned i;
    if(mt_cache_owner!=s||!s->frame||s->frame!=mt_cache_frame+1||mt_cache_target!=s->target||
       s->position<mt_cache_begin||s->position>=mt_cache_end){
        unsigned distance=s->profile->hop_frames-s->position;
        float future_amount=s->amount;
        if(distance>32)distance=32;
        mt_cache_begin=s->position;mt_cache_end=s->position+distance;
        if(s->remaining)future_amount=s->remaining<=distance?s->target:s->amount+distance*s->step;
        mt_gains_at(s,mt_cache_begin,s->amount,mt_gain_begin);
        mt_gains_at(s,mt_cache_end,future_amount,mt_gain_end);
        mt_cache_target=s->target;mt_cache_owner=s;
    }
    {float u=(float)(s->position-mt_cache_begin)/(mt_cache_end-mt_cache_begin);
     for(i=0;i<s->profile->count;++i)out[i]=mt_gain_begin[i]+u*(mt_gain_end[i]-mt_gain_begin[i]);}
    mt_cache_frame=s->frame;
}
#endif
static int valid(float amount){return isfinite(amount)&&amount>=0&&amount<=1.3f;}
/* Same declared Gaussian stream as the Python oracle; independent state,
   no coupling to the existing DNA/residual generators. */
static float uniform(MtEnvelope *s) {
    uint64_t x=s->rng;x^=x>>12;x^=x<<25;x^=x>>27;s->rng=x;
    return (((x*UINT64_C(2685821657736338717))>>11)+.5f)/9007199254740992.f;
}
static float gaussian(MtEnvelope *s) {
    float radius,angle;
    if(s->has_spare){s->has_spare=0;return s->spare;}
    radius=sqrtf(-2*logf(uniform(s)));angle=2*MT_PI*uniform(s);
    s->spare=radius*sinf(angle);s->has_spare=1;return radius*cosf(angle);
}
static void draw(MtEnvelope *s,float *out) {
    unsigned i,j;float normal[MT_MAX_MODES];
    for(j=0;j<s->profile->count;++j)normal[j]=gaussian(s);
    for(i=0;i<s->profile->count;++i) {
        float value=0;
        for(j=0;j<s->profile->count;++j)value+=s->profile->factor[i][j]*normal[j];
        out[i]=value;
    }
}
static void next(MtEnvelope *s) {
    unsigned i;float fresh[MT_MAX_MODES];draw(s,fresh);
    for(i=0;i<s->profile->count;++i)
        s->right[i]=s->profile->alpha*s->left[i]+s->innovation_scale*fresh[i];
}
int mt_envelope_init(MtEnvelope *out,const MtProfile *p,uint64_t seed,float amount) {
    MtEnvelope s;unsigned i,j;
    if(!out||!valid(amount)||!mt_profile_valid(p))return 0;
    memset(&s,0,sizeof s);s.profile=p;
    s.rng=seed^UINT64_C(0x8CB92BA72F3D8DD7);if(!s.rng)s.rng=1;
    s.amount=s.target=amount;s.innovation_scale=sqrtf(1-p->alpha*p->alpha);
    for(i=0;i<p->count;++i)for(j=0;j<p->count;++j)s.variance[i]+=p->factor[i][j]*p->factor[i][j];
    draw(&s,s.left);next(&s);*out=s;return 1;
}
int mt_envelope_set(MtEnvelope *s,float amount) {
    if(!s||!s->profile||!valid(amount))return 0;
    if(amount!=s->target) {
        s->target=amount;s->remaining=MT_RAMP_FRAMES;s->step=(amount-s->amount)/MT_RAMP_FRAMES;
    }
    return 1;
}
int mt_envelope_tick(MtEnvelope *s,float *gain) {
    unsigned i;float u,v;
    if(!s||!s->profile||!gain)return 0;
    if(s->remaining){if(!--s->remaining)s->amount=s->target;else s->amount+=s->step;}
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    if(s->profile->hop_frames>=64)mt_gains_cached(s,gain);
    else {
#endif
    u=.5f-.5f*cosf(MT_PI*(float)s->position/s->profile->hop_frames);
    v=sqrtf((1-u)*(1-u)+u*u+2*s->profile->alpha*u*(1-u));
    for(i=0;i<s->profile->count;++i) {
        float z=((1-u)*s->left[i]+u*s->right[i])/v;
        /* Gaussian marginal E[gain^2]=1. This is not finite-take loudness
           matching, nor a claim that windowed source magnitude is true AM. */
        gain[i]=expf(s->amount*z-s->amount*s->amount*s->variance[i]);
    }
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    }
#endif
    ++s->frame;
    if(++s->position==s->profile->hop_frames) {
        s->position=0;memcpy(s->left,s->right,sizeof s->left);next(s);
    }
    return 1;
}
