#include "voice.h"
#include "spectral_texture/voice.h"
#include "modal_texture/envelope.h"
#include <stdlib.h>
struct SpmVoice {
    SfBank *bank;SfVoice *spectral;MtEnvelope motion;
    unsigned count,map[SF_MAX_BANDS];double right[SF_MAX_BANDS];
};
void spm_voice_destroy(SpmVoice *v) {
    if(v){sf_voice_destroy(v->spectral);sf_bank_destroy(v->bank);free(v);}
}
SpmVoice *spm_voice_create(const SpmProfile *p,uint64_t seed,double amount) {
    SpmVoice *v;unsigned i;
    if(!spm_profile_valid(p))return NULL;
    v=calloc(1,sizeof *v);if(!v)return NULL;
    if(!mt_envelope_init(&v->motion,p->motion,seed,amount)||
       !(v->bank=sf_bank_create(p->spectral))||!(v->spectral=sf_voice_create(v->bank,seed))) {
        spm_voice_destroy(v);return NULL;
    }
    v->count=p->spectral->count;
    for(i=0;i<v->count;++i){v->map[i]=p->map[i];v->right[i]=p->spectral->band[i].right_over_left;}
    return v;
}
int spm_voice_set(SpmVoice *v,double amount){return v&&mt_envelope_set(&v->motion,amount);}
int spm_voice_tick(SpmVoice *v,double out[2],double *bands) {
    unsigned i;double raw[2],parts[SF_MAX_BANDS],gain[MT_MAX_MODES],left=0,right=0;
    if(!v||!out)return 0;
    if(!sf_voice_tick(v->spectral,raw,parts)||!mt_envelope_tick(&v->motion,gain))return 0;
    if(v->motion.amount==0) {
        out[0]=raw[0];out[1]=raw[1];
        if(bands)for(i=0;i<v->count;++i)bands[i]=parts[i];
        return 1;
    }
    for(i=0;i<v->count;++i) {
        double x=parts[i];if(v->map[i])x*=gain[v->map[i]-1];
        if(bands)bands[i]=x;left+=x;right+=x*v->right[i];
    }
    out[0]=left;out[1]=right;return 1;
}
