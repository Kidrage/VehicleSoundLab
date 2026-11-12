#include "drive_recipe/voice.h"
#include "resonant_source/voice.h"
#include "resonant_detail_io/profile.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define PI 3.14159265358979323846
#define CHECK(x) do{if(!(x)){fprintf(stderr,"full recipe line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static SdProfile original,prepared,low,synthetic[2],synth_low;
static SaBank dna_bank;static DrsBank detail_bank;static DrcBank recipe,saved;
static RdtProfile detail;static SaVoice dna;static DrcVoice body,muted;static DrsVoice resonance;
static RssVoice reference;
static int full_recipe(void) {
    const SdProfile *p[]={&original},*l[]={&low};const RdtProfile *r[]={&detail};
    RssColour colour={.35,1200,1900};double scale=1.6658265329883064;
    RssConfig cfg={0};RssControl ctl={{1,1,1,1,1,0},1};unsigned n,c,seed;double maximum=0;
    CHECK(sd_profile_load("voices/dna_bank_v1/V10 Exterior.model",&original));
    CHECK(sd_profile_load("voices/coherent_low_v1/measured_phase.model",&low));
    CHECK(rdt_profile_load("voices/resonant_detail_c_v1/moving_35.rdetail",&detail));
    CHECK(sa_bank_init(&dna_bank,p,1,0)&&drs_bank_init(&detail_bank,&dna_bank,r));
    CHECK(drc_bank_init(&recipe,&dna_bank,&detail_bank,&colour,l,&scale));
    saved=recipe;low.base_hz+=1;
    CHECK(!drc_bank_init(&recipe,&dna_bank,&detail_bank,&colour,l,&scale)&&!memcmp(&recipe,&saved,sizeof recipe));low.base_hz-=1;
    CHECK(!drc_bank_init(&recipe,&dna_bank,NULL,&colour,l,&scale)&&!memcmp(&recipe,&saved,sizeof recipe));
    CHECK(rss_profile_prepare(&prepared,&original,&colour));
    cfg.source.dna=&prepared;cfg.source.low=&low;cfg.source.low_scale=scale;cfg.detail=&detail;
    for(seed=0;seed<3;++seed) {
        cfg.source.dna_seed=cfg.source.low_seed=48271+seed;cfg.detail_seed=8121907+seed;
        CHECK(rss_voice_init(&reference,&cfg,&ctl));
        CHECK(sa_voice_init(&dna,&dna_bank,cfg.source.dna_seed,original.base_hz,1,1));
        CHECK(drc_voice_init(&body,&recipe,&dna_bank,&detail_bank,cfg.source.low_seed,1));
        CHECK(drc_voice_init(&muted,&recipe,&dna_bank,&detail_bank,cfg.source.low_seed,0));
        CHECK(drs_voice_init(&resonance,&detail_bank,&dna_bank,cfg.detail_seed,1));
        for(n=0;n<16384;++n) {
            double shape[SD_MAX_HARMONICS],out[2],tap[2],phase=dna.phase;HbBand band=hb_band_default();
            DrcFrame b,z;DrsFrame d;RssFrame old;
            CHECK(drc_shape(&recipe,&dna,&resonance,shape));
            CHECK(sa_voice_tick_shaped_body(&dna,&band,shape,1,out,tap));
            CHECK(drc_voice_tick(&body,&dna,phase,&b)&&drc_voice_tick(&muted,&dna,phase,&z));
            CHECK(drs_voice_tick(&resonance,&dna,phase,&d)&&rss_voice_tick(&reference,&old));
            CHECK(b.raw[0]==z.raw[0]&&b.raw[1]==z.raw[1]&&z.output[0]==0&&z.output[1]==0&&b.support==1);
            for(c=0;c<2;++c) {
                double full=(out[c]+b.output[c])+d.output[c],error=fabs(full-old.mix[c]);
                if(error>maximum)maximum=error;CHECK(error<2e-10);
                CHECK(fabs(b.output[c]-old.source.low[c])<2e-11);
            }
        }
        CHECK(!memcmp(body.texture,muted.texture,sizeof body.texture));
    }
    /* Disabling detail restores original harmonic power, independently of LF. */
    resonance.amount=resonance.target=0;
    {double shape[SD_MAX_HARMONICS];CHECK(drc_shape(&recipe,&dna,&resonance,shape));
        for(n=0;n<dna_bank.harmonics;++n)CHECK(shape[n]==1);}
    resonance.amount=resonance.target=1;dna.root_hz=dna.root_target=original.base_hz*.8;
    {double shape[SD_MAX_HARMONICS],out[2],phase=dna.phase;DrcFrame b;
        CHECK(drc_shape(&recipe,&dna,&resonance,shape));for(n=0;n<dna_bank.harmonics;++n)CHECK(shape[n]==1);
        sa_voice_tick(&dna,out);CHECK(drc_voice_tick(&body,&dna,phase,&b)&&b.support==0&&b.raw[0]==0);}
    printf("PASS: unchanged moving35 full recipe three seeds, external phase, mute clocks, local withdrawal max %.17g FS\n",maximum);
    return 0;
}
static int different_models(void) {
    const SdProfile *p[2]={synthetic,synthetic+1},*l[2]={&synth_low,NULL};
    RssColour colour[2]={{0,1200,1900},{0,1200,1900}};double scales[2]={1,1};unsigned a,n;
    memset(synthetic,0,sizeof synthetic);memset(&synth_low,0,sizeof synth_low);
    for(a=0;a<2;++a) {
        synthetic[a].rate=48000;synthetic[a].window=1024;synthetic[a].hop=256;
        synthetic[a].harmonics=16;synthetic[a].base_hz=40+10*a;
        synthetic[a].harmonic[0].mean[0]=.1;
    }
    synth_low=synthetic[0];synth_low.harmonics=1;
    synth_low.harmonic[0].mean[0]=.1*cos(.2);synth_low.harmonic[0].mean[1]=.1*sin(.2);
    synth_low.harmonic[0].mean[2]=.07*cos(.6);synth_low.harmonic[0].mean[3]=.07*sin(.6);
    CHECK(sa_bank_init(&dna_bank,p,2,0)&&drc_bank_init(&recipe,&dna_bank,NULL,colour,l,scales));
    dna_bank.offset[0]=.31;
    CHECK(sa_voice_init(&dna,&dna_bank,91,40,0,1)&&drc_voice_init(&body,&recipe,&dna_bank,NULL,91,1));
    for(n=0;n<128;++n) {
        double phase=.3+n*.01;DrcFrame b;
        CHECK(drc_voice_tick(&body,&dna,phase,&b));
        CHECK(fabs(b.output[0]-.1*cos(phase+.31+.2))<1e-15);
        CHECK(fabs(b.output[1]-.07*cos(phase+.31+.6))<1e-15);
    }
    dna.root_hz=dna.root_target=50;
    {DrcFrame b;double prior=body.texture[0].fraction;
        CHECK(drc_voice_tick(&body,&dna,.4,&b)&&b.output[0]==0&&b.support==0&&body.texture[0].fraction!=prior);}
    CHECK(!drc_voice_set(&body,NAN)&&!drc_voice_tick(&body,&dna,-1,NULL));
    puts("PASS: distinct synthetic bank, shared origin, L/R phase, missing low anchor and advancing clocks");return 0;
}
int main(void){CHECK(!full_recipe());CHECK(!different_models());return 0;}
