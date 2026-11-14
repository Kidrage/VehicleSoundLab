#include "decel_models.h"
#include "drive_recipe/shape.h"
#include "stereo_resonance/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"stereo recipe%d: %s\n",__LINE__,#x);return 1;}}while(0)
static CdmModels model;
static DrsBank bad;
static DrcBank saved,recipe;
static SaVoice dna;
static DrsVoice on,off;
static RvsVoice direct;
/* Independent piecewise reference; never calls the recipe's mask helpers. */
static double support(double ratio) {
    double t;if(ratio<=.9||ratio>=1.1)return 0;
    if(ratio<.96)t=(ratio-.9)/.06;else if(ratio>1.04)t=(1.1-ratio)/.06;else return 1;
    return t*t*(3-2*t);
}
static double reduction(double hz) {
    double t=(hz-1200)/700;if(t<=0)return 0;if(t>=1)return .35;
    return .35*t*t*(3-2*t);
}
int main(void) {
    RssColour colour={.35,1200,1900};HbBand band=hb_band_default();double maximum=0;
    CHECK(cdm_models_load(&model));saved=model.recipe;recipe=saved;
    CHECK(drc_bank_valid(&recipe,&model.bank,&model.resonance));
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
    CHECK(sa_voice_init(&dna,&model.bank,48271,model.dna.base_hz,1,1));
    CHECK(drs_voice_init(&on,&model.resonance,&model.bank,619,.6));
    CHECK(drs_voice_init(&off,&model.resonance,&model.bank,619,0));
    CHECK(rvs_voice_init(&direct,&model.detail,619,1));
    for(unsigned n=0;n<8192;++n) {
        static const double ratios[]={.8,.9,.93,1,1.07,1.1,1.2,1};
        double shape[SD_MAX_HARMONICS],out[2],tap[2],ref[2],phase=dna.phase;
        double next,amount,s;DrsFrame x,y;
        if(n%1024==0)CHECK(sa_voice_set(&dna,ratios[n/1024]*model.dna.base_hz,1,1));
        if(n==1024)CHECK(drs_voice_set(&on,0));if(n==3072)CHECK(drs_voice_set(&on,1));
        next=dna.root_hz+dna.follow*(dna.root_target-dna.root_hz);
        amount=on.amount+on.follow*(on.target-on.amount);s=support(next/model.dna.base_hz);
        CHECK(drc_shape(&recipe,&dna,&on,shape));
        for(unsigned h=0;h<model.bank.harmonics;++h) {
            double wanted=sqrt(1-s*s*amount*amount*reduction((h+1)*model.dna.base_hz));
            double error=fabs(wanted-shape[h]);maximum=fmax(maximum,error);CHECK(error<2e-15);
        }
        CHECK(sa_voice_tick_shaped_body(&dna,&band,shape,1,out,tap));
        CHECK(drs_voice_tick(&on,&dna,phase,&x)&&drs_voice_tick(&off,&dna,phase,&y));
        CHECK(rvs_voice_tick(&direct,ref,NULL));CHECK(fabs(x.support-s*s)<2e-14);
        for(unsigned c=0;c<2;++c) {
            CHECK(fabs(x.raw[c]-ref[c]*s)<2e-14&&x.raw[c]==y.raw[c]&&y.output[c]==0);
            CHECK(fabs(x.output[c]-ref[c]*s*amount)<2e-14&&isfinite(out[c]));
        }
    }
    CHECK(on.stereo[0].frame==8192&&off.stereo[0].frame==8192);
    CHECK(!memcmp(on.stereo[0].history,off.stereo[0].history,sizeof direct.history));
    CHECK(!memcmp(on.stereo[0].excitation,off.stereo[0].excitation,sizeof direct.excitation));
    /* Zero detail restores the unshaped source, not merely a silent residual. */
    on.amount=on.target=0;
    for(unsigned k=0;k<2;++k) {
        double shape[SD_MAX_HARMONICS],x[2],y[2],tap[2];SaVoice plain=dna;
        if(k)dna.root_hz=dna.root_target=model.dna.base_hz*.8;
        plain=dna;CHECK(drc_shape(&recipe,&dna,&on,shape));
        for(unsigned h=0;h<model.bank.harmonics;++h)CHECK(shape[h]==1);
        CHECK(sa_voice_tick_shaped_body(&dna,&band,shape,1,x,tap));sa_voice_tick(&plain,y);
        CHECK(!memcmp(x,y,sizeof x)&&!memcmp(&dna,&plain,sizeof dna));
    }
    printf("PASS stereo recipe: independent withdrawal oracle %.3g, bad/missing rejection, direct kernel, muted clocks and exact zero bypass\n",maximum);
    return 0;
}
