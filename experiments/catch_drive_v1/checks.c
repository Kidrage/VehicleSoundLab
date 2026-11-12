#include "atlas_take/parameters.h"
#include "atlas_drive/render.h"
#include "core/engine.h"
#include "profiles/lifecycle.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"catch drive line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define N 240
static SdProfile profile;static SaBank bank;
static AdRender render[6];static VslEngine engine[6];
static float out[6][12*N],raw[6][2*N],dna[6][2*N],delta[6][2*N];
static double oracle_input[2*N],oracle_delta[2*N];
int main(void) {
    const SdProfile *models[1]={&profile};CbProfile p={2,.7,1.2,.005,.035,{{98,1.1,1.2},{381,1.27,3.26}}};
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl c={{VSL_BENCH,0,0,0,0,0,850,0,0,0},{.2,1,0,1,0,0,1,0}};
    CbVoice oracle;unsigned n,i,j,h,mask=0,count;double peak=0,error=0,mix_error=0;
    const AtField *fields=at_fields(&count);CHECK(count==27&&!strcmp(fields[count-1].name,"catch_gain"));
    profile.rate=48000;profile.window=1024;profile.hop=256;profile.base_hz=35;profile.harmonics=24;
    for(h=0;h<24;++h){profile.harmonic[h].mean[0]=.02/(h+1);profile.harmonic[h].mean[2]=.017/(h+1);}
    CHECK(sa_bank_init(&bank,models,1,0));config.root_per_rpm=35./850;config.scene_mode=AD_SCENE_STEREO_BED;
    for(i=0;i<6;++i) {
        config.catch_profile=i?&p:NULL;config.channels=i==2?12:2;
        c.mix.catch_gain=i&&i!=5?.7:0;c.mix.body_mix=i==4?1:0;
        CHECK(ad_render_init(render+i,engine+i,&config,&c));
    }
    CHECK(cb_voice_init(&oracle,&p,.7));
    for(n=0;n<1200;++n) {
        double t=n*.005,u;int gate;
        c.drive.ignition=(t>=.05&&t<2.25)||(t>=3&&t<5.4);
        c.drive.start_id=t>=3.2?2:t>=.15?1:0;
        for(i=0;i<6;++i) {
            AdCapture cap={0};cap.dna_raw=raw[i];cap.dna=dna[i];cap.catch_bloom=delta[i];
            c.mix.catch_gain=i&&i!=5?.7:0;c.mix.body_mix=i==4?1:0;
            CHECK(ad_render_set(render+i,&c));
            if(i!=3)CHECK(ad_render_process(render+i,out[i],N,&cap));
            else for(j=0;j<N;++j){cap.dna_raw=raw[i]+2*j;cap.dna=dna[i]+2*j;cap.catch_bloom=delta[i]+2*j;
                CHECK(ad_render_process(render+i,out[i]+2*j,1,&cap));}
            CHECK(!memcmp(&engine[0].drive,&engine[i].drive,sizeof engine[0].drive));
            CHECK(!memcmp(raw[0],raw[i],sizeof raw[0]));
            for(j=0;j<N*(unsigned)render[i].config.channels;++j)CHECK(isfinite(out[i][j]));
        }
        CHECK(!memcmp(out[0],out[5],2*N*sizeof(float))&&!memcmp(dna[0],dna[1],2*N*sizeof(float)));
        CHECK(!memcmp(delta[1],delta[2],2*N*sizeof(float))&&!memcmp(delta[1],delta[3],2*N*sizeof(float)));
        CHECK(!memcmp(delta[1],delta[4],2*N*sizeof(float))&&!memcmp(out[1],out[3],2*N*sizeof(float)));
        CHECK(!memcmp(&render[1].catch_bloom,&render[3].catch_bloom,sizeof oracle));
        CHECK(!memcmp(render[1].catch_bloom.filter,render[5].catch_bloom.filter,sizeof oracle.filter));
        gate=engine[1].drive.lifecycle==VSL_CATCH;
        u=gate?engine[1].drive.life_seconds/.65:0;
        CHECK(cb_voice_set(&oracle,gate,u,.7));
        for(j=0;j<N*2;++j)oracle_input[j]=dna[1][j];
        CHECK(cb_voice_process(&oracle,oracle_input,oracle_delta,N));
        for(j=0;j<N;++j) {
            unsigned k;
            CHECK(out[1][2*j]==out[2][12*j]&&out[1][2*j+1]==out[2][12*j+1]);
            for(k=2;k<12;++k)CHECK(out[2][12*j+k]==0);
            for(k=0;k<2;++k){double d=delta[1][2*j+k];
                error=fmax(error,fabs(d-oracle_delta[2*j+k]));peak=fmax(peak,fabs(d));
                mix_error=fmax(mix_error,fabs(out[1][2*j+k]-.2*(dna[1][2*j+k]+d)));
                CHECK(delta[5][2*j+k]==0);}
        }
        mask|=1u<<engine[1].drive.lifecycle;
    }
    CHECK(mask==63&&engine[1].drive.start_events==2&&peak>.001&&error<2e-8&&mix_error<2e-8);
    config.catch_profile=NULL;config.channels=2;c.mix.catch_gain=.1;
    CHECK(!ad_render_init(render,engine,&config,&c)&&!ad_render_set(render,&c));
    config.catch_profile=&p;c.mix.catch_gain=0;CHECK(ad_render_init(render,engine,&config,&c));
    c.mix.catch_gain=NAN;CHECK(!ad_render_set(render,&c));
    printf("PASS: two starts,zero identity,independent body amount,one-sample chunks,2/12 once-only front route,oracle %.9g,mix %.9g\n",error,mix_error);return 0;
}
