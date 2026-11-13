#include "spectral_motion/voice.h"
#include "spectral_texture/voice.h"
#include "resonant_detail/excitation.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line%u: %s\n",(unsigned)__LINE__,#x);return 1;}}while(0)
static SfProfile spectral;
static MtProfile motion;
static void prepare(void) {
    unsigned i;memset(&spectral,0,sizeof spectral);memset(&motion,0,sizeof motion);
    spectral.rate=48000;spectral.count=3;spectral.warmup_frames=13;
    for(i=0;i<3;++i) {
        SfBand *b=spectral.band+i;b->count=2;b->taps[0]=.8;b->taps[1]=.6;
        b->gain=.01*(i+1);b->right_over_left=i==1?-.3:.7;
    }
    motion.rate=48000;motion.count=1;motion.hop_frames=17;motion.alpha=.7;motion.factor[0][0]=.1;
}
static int controls(void) {
    SpmProfile p={&spectral,&motion,{0,1,1}};SfBank *bank;SfVoice *old;SpmVoice *a,*b;
    unsigned n;double x[2],y[2],z[2],parts[SF_MAX_BANDS],base[SF_MAX_BANDS];
    CHECK(spm_profile_valid(&p));p.map[2]=2;CHECK(!spm_profile_valid(&p));p.map[2]=1;
    p.map[1]=p.map[2]=0;CHECK(!spm_profile_valid(&p));p.map[1]=p.map[2]=1;
    CHECK(!spm_voice_create(&p,11,NAN)&&!spm_voice_create(&p,11,-.01)&&!spm_voice_create(&p,11,1.01));
    bank=sf_bank_create(&spectral);old=sf_voice_create(bank,11);a=spm_voice_create(&p,11,0);b=spm_voice_create(&p,11,0);
    CHECK(old&&a&&b);CHECK(!spm_voice_tick(a,NULL,NULL)&&!spm_voice_set(a,NAN)&&!spm_voice_set(a,-1));
    for(n=0;n<3001;++n) {
        CHECK(spm_voice_tick(a,x,parts)&&spm_voice_tick(b,y,NULL)&&sf_voice_tick(old,z,base));
        CHECK(!memcmp(x,y,sizeof x)&&!memcmp(x,z,sizeof x)&&!memcmp(parts,base,3*sizeof(double)));
    }
    for(n=0;n<3001;++n) {
        CHECK(spm_voice_set(a,1)); /* Must not restart18ms ramp each sample. */
        if(!n)CHECK(spm_voice_set(b,1));
        CHECK(spm_voice_tick(a,x,parts)&&spm_voice_tick(b,y,NULL)&&sf_voice_tick(old,z,base));
        CHECK(!memcmp(x,y,sizeof x));CHECK(parts[0]==base[0]);
        if(fabs(base[1])>1e-10&&fabs(base[2])>1e-10)CHECK(fabs(parts[1]/base[1]-parts[2]/base[2])<1e-12);
    }
    CHECK(spm_voice_set(a,0));
    for(n=0;n<1000;++n) {
        CHECK(spm_voice_tick(a,x,NULL)&&sf_voice_tick(old,z,NULL));
        if(n>=863)CHECK(!memcmp(x,z,sizeof x));
    }
    sf_voice_destroy(old);sf_bank_destroy(bank);spm_voice_destroy(a);spm_voice_destroy(b);return 0;
}
static int copied_spectral(void) {
    SpmProfile p={&spectral,&motion,{0,1,1}};SpmVoice *a,*b;double x[2],y[2];unsigned n;
    a=spm_voice_create(&p,149921,.5);b=spm_voice_create(&p,149921,.5);CHECK(a&&b);
    memset(&spectral,0,sizeof spectral);memset(p.map,0,sizeof p.map);
    for(n=0;n<3001;++n){CHECK(spm_voice_tick(a,x,NULL)&&spm_voice_tick(b,y,NULL));CHECK(!memcmp(x,y,sizeof x));}
    spm_voice_destroy(a);spm_voice_destroy(b);return 0;
}
int main(void){prepare();CHECK(!controls());prepare();CHECK(!copied_spectral());puts("spectral_motion_contracts_passed=1");return 0;}
