#include "models.h"
#include "fine_idle_layer/state.h"
#include "modal_texture/voice.h"
#include "spectral_texture/voice.h"
#include <stdio.h>
#include <math.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"fine idle layer line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static FidModels models;
int main(void) {
    FiState *s,*muted;SfBank *bank;SfVoice *detail;MtVoice modal;
    double amount=.7,position=0,start=0,target=0,follow=1-exp(-1/(.018*48000));
    unsigned duration=0,count=0,n;int previous=0;
    CHECK(fid_models_load(&models));
    s=fi_state_create(&models.idle,149921,.7,.5,1);muted=fi_state_create(&models.idle,149921,0,.5,1);
    CHECK(s&&muted);bank=sf_bank_create(&models.detail);detail=sf_voice_create(bank,149921);
    CHECK(bank&&detail&&mt_voice_init(&modal,&models.modal,&models.motion,149921,1,1,.5));
    for(n=0;n<96000;++n) {
        int gate=(n>=500&&n<900)||(n>=1100&&n<1300)||n>=2000;
        double value=n<700?.7:n<2500?0:1,env=n>7000&&n<9000?0:.63,core[2],fine[2],weight;
        FiFrame f,z;
        if(gate!=previous){start=position;target=gate;duration=gate?models.idle.attack_frames:models.idle.release_frames;count=0;previous=gate;}
        if(count<duration){++count;position=count==duration?target:start+(target-start)*count/duration;}
        amount+=follow*(value-amount);weight=position*position*(3-2*position)*amount;
        CHECK(fi_state_tick(s,gate,value,.5,1,env,&f)&&fi_state_tick(muted,0,0,.5,1,0,&z));
        CHECK(mt_voice_tick(&modal,core)&&sf_voice_tick(detail,fine,NULL));
        CHECK(fabs(f.weight-weight)<1e-12&&f.weight>=0&&f.weight<=1&&f.keep==1-f.weight);
        for(unsigned c=0;c<2;++c) {
            CHECK(f.modal[c]==core[c]&&f.detail[c]==fine[c]&&f.raw[c]==core[c]+fine[c]);
            CHECK(f.raw[c]==z.raw[c]&&fabs(f.output[c]-f.raw[c]*(env*weight*models.idle.level_gain))<1e-12);
        }
    }
    /* Bad requests must not consume a random sample or alter output. */
    {FiFrame f={0},z={0},before=f;CHECK(!fi_state_tick(s,1,NAN,.5,1,1,&f)&&!memcmp(&before,&f,sizeof f));
     CHECK(!fi_state_tick(s,2,1,.5,1,1,&f));
     CHECK(fi_state_tick(s,1,1,.5,1,1,&f)&&fi_state_tick(muted,0,0,.5,1,0,&z));CHECK(!memcmp(f.raw,z.raw,sizeof f.raw));}
    fi_state_destroy(s);fi_state_destroy(muted);sf_voice_destroy(detail);sf_bank_destroy(bank);
    /* New controls are finite ramps; different gate/amount must not restart RNG. */
    s=fi_state_create(&models.idle,32819,1,0,0);muted=fi_state_create(&models.idle,32819,0,0,0);CHECK(s&&muted);
    for(n=0;n<9000;++n) {
        FiFrame f,z;double motion=n>=100?1:0,d=n>=300?1:0;
        CHECK(fi_state_tick(s,1,1,motion,d,1,&f)&&fi_state_tick(muted,0,0,motion,d,0,&z));
        CHECK(!memcmp(f.raw,z.raw,sizeof f.raw));
        for(unsigned c=0;c<2;++c)CHECK(isfinite(f.output[c]));
    }
    fi_state_destroy(s);fi_state_destroy(muted);fi_state_destroy(NULL);
    puts("PASS frozen C source parity, independent fade/amount oracle, silent clocks, finite controls and invalid-call transaction");return 0;
}
