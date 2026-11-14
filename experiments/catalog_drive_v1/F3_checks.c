#include "F3_models.h"
#include "drive_recipe/shape.h"
#include "stereo_resonance/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"additive recipe%d: %s\n",__LINE__,#x);return 1;}}while(0)
static F3mModels model;
static DrsBank bad;
static DrcBank saved,recipe;
static SaVoice shaped,plain;
static DrsVoice on,off;
static DrcVoice low;
static RvsVoice direct;
/* Independent reference for the declared local fade; no engine-state claim. */
static double support(double ratio) {
    double t;if(ratio<=.9||ratio>=1.1)return 0;
    if(ratio<.96)t=(ratio-.9)/.06;else if(ratio>1.04)t=(1.1-ratio)/.06;else return 1;
    return t*t*(3-2*t);
}
int main(void) {
    RssColour colour={0,1200,1900};HbBand band=hb_band_default();
    double maximum=0,energy=0,stereo_difference=0;
    CHECK(!f3m_models_load(NULL)&&f3m_models_load(&model));saved=model.recipe;recipe=saved;
    CHECK(model.bank.count==1&&model.bank.profile[0]==&model.dna);
    CHECK(model.dna.harmonics==288&&model.dna.components==12&&model.detail.count==10);
    CHECK(!model.recipe.has_low[0]&&model.recipe.colour[0].power_reduction==0);
    CHECK(drc_bank_valid(&recipe,&model.bank,&model.resonance));
    CHECK(!drc_bank_valid(&recipe,&model.bank,NULL));
    CHECK(!drc_bank_init(&recipe,&model.bank,NULL,&colour,NULL,NULL)&&!memcmp(&recipe,&saved,sizeof recipe));
    for(unsigned mode=0;mode<5;++mode) {
        bad=model.resonance;
        switch(mode) {
        case 0:bad.enabled[0]=0;bad.kind[0]=DRS_NONE;break;
        case 1:bad.kind[0]=99;break;
        case 2:bad.stereo[0].band[0].certificate[0][0]=-1;break;
        case 3:bad.root[0]+=1;break;
        default:bad.stereo[0].base_hz+=1;break;
        }
        CHECK(!drc_bank_valid(&recipe,&model.bank,&bad));
        CHECK(!drc_bank_init(&recipe,&model.bank,&bad,&colour,NULL,NULL)&&!memcmp(&recipe,&saved,sizeof recipe));
    }
    CHECK(sa_voice_init(&shaped,&model.bank,48271,model.dna.base_hz,1,1));plain=shaped;
    CHECK(drs_voice_init(&on,&model.resonance,&model.bank,8121907,.5));
    CHECK(drs_voice_init(&off,&model.resonance,&model.bank,8121907,0));
    CHECK(rvs_voice_init(&direct,&model.detail,8121907,1));
    CHECK(drc_voice_init(&low,&model.recipe,&model.bank,&model.resonance,48271,0));
    for(unsigned n=0;n<8192;++n) {
        static const double ratios[]={.8,.9,.93,1,1.07,1.1,1.2,1};
        double gain[SD_MAX_HARMONICS],x[2],y[2],tap[2],ref[2],phase=shaped.phase;
        double amount=on.amount+on.follow*(on.target-on.amount),s;
        DrsFrame a,b;DrcFrame lf;
        if(n%1024==0) {
            double root=ratios[n/1024]*model.dna.base_hz;
            CHECK(sa_voice_set(&shaped,root,1,1)&&sa_voice_set(&plain,root,1,1));
        }
        if(n==1024){CHECK(drs_voice_set(&on,0));amount=on.amount+on.follow*(on.target-on.amount);}
        if(n==3072){CHECK(drs_voice_set(&on,1));amount=on.amount+on.follow*(on.target-on.amount);}
        CHECK(drc_shape(&recipe,&shaped,&on,gain));
        for(unsigned h=0;h<model.bank.harmonics;++h)CHECK(gain[h]==1);
        CHECK(sa_voice_tick_shaped_body(&shaped,&band,gain,1,x,tap));sa_voice_tick(&plain,y);
        CHECK(!memcmp(x,y,sizeof x)&&!memcmp(&shaped,&plain,sizeof shaped));
        CHECK(drc_voice_tick(&low,&shaped,phase,&lf));
        CHECK(lf.raw[0]==0&&lf.raw[1]==0&&lf.output[0]==0&&lf.output[1]==0&&lf.support==0);
        CHECK(drs_voice_tick(&on,&shaped,phase,&a)&&drs_voice_tick(&off,&shaped,phase,&b));
        CHECK(rvs_voice_tick(&direct,ref,NULL));s=support(shaped.root_hz/model.dna.base_hz);
        CHECK(fabs(a.support-s*s)<2e-14);
        for(unsigned c=0;c<2;++c) {
            double error=fabs(a.raw[c]-ref[c]*s);maximum=fmax(maximum,error);CHECK(error<2e-14);
            CHECK(a.raw[c]==b.raw[c]&&b.output[c]==0&&fabs(a.output[c]-ref[c]*s*amount)<2e-14);
            CHECK(isfinite(x[c]+a.output[c]));energy+=a.output[c]*a.output[c];
        }
        stereo_difference+=(ref[0]-ref[1])*(ref[0]-ref[1]);
    }
    CHECK(energy>0&&stereo_difference>0&&low.frame==8192);
    CHECK(on.stereo[0].frame==8192&&off.stereo[0].frame==8192);
    CHECK(!memcmp(on.stereo[0].history,off.stereo[0].history,sizeof direct.history));
    CHECK(!memcmp(on.stereo[0].excitation,off.stereo[0].excitation,sizeof direct.excitation));
    printf("PASS additive recipe: DNA samples/state exact, no LF, stereo direct error%.3g, local support/muted clocks, transactional invalid rejection\n",maximum);
    return 0;
}
