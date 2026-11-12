#include "atlas_drive/render.h"
#include "core/engine.h"
#include "start_texture/voice.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"startup drive line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define N 240
static SdProfile dna;static SaBank bank;static StProfile profile;
static AdRender render[3];static VslEngine engine[3];static StVoice voice;
static float out[3][12*N],startup[3][2*N];
static double initial_hz[SR_MAX_OSCILLATORS];
int main(void) {
    const SdProfile *models[1]={&dna};unsigned n,i,k,b;double t;
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl c={{VSL_BENCH,0,0,0,0,0,1000,0,0,0},{.2,1,0,1,0,0,1,0}};
    profile.spectrum.rate=48000;profile.spectrum.bands=2;profile.spectrum.partials=8;
    profile.spectrum.band[0]=(SrBand){300,900,{.01,.02},{.4,-.3}};
    profile.spectrum.band[1]=(SrBand){1000,2000,{0,.01},{0,0}};
    profile.has_finish=1;profile.finish=profile.spectrum;
    profile.finish.band[0]=(SrBand){300,900,{.04,.03},{-.2,.6}};
    profile.finish.band[1]=(SrBand){1000,2000,{.02,0},{0,0}};
    profile.attack_seconds=.005;profile.release_seconds=.035;
    CHECK(st_voice_init(&voice,&profile,19,1)&&st_voice_set(&voice,1,1)&&st_voice_position(&voice,.3));
    {double x[2];for(n=0;n<96000;++n)CHECK(st_voice_process(&voice,x,NULL,1));}
    t=voice.position;CHECK(fabs(t-.3)<1e-13);
    /* Independent PSD identities, including singular endpoints and complex sign. */
    for(b=0;b<2;++b) {
        const SrBand *a=&profile.spectrum.band[b],*z=&profile.finish.band[b];const double *v=voice.coefficient[b];
        double l=(1-t)*a->power[0]+t*z->power[0],r=(1-t)*a->power[1]+t*z->power[1];
        double re=(1-t)*a->coherence[0]*sqrt(a->power[0]*a->power[1])+t*z->coherence[0]*sqrt(z->power[0]*z->power[1]);
        double im=(1-t)*a->coherence[1]*sqrt(a->power[0]*a->power[1])+t*z->coherence[1]*sqrt(z->power[0]*z->power[1]);
        CHECK(fabs(v[0]*v[0]-l)<1e-14&&fabs(v[1]*v[1]+v[2]*v[2]+v[3]*v[3]-r)<1e-14);
        CHECK(fabs(v[0]*v[1]-re)<1e-14&&fabs(v[0]*v[2]-im)<1e-14);
    }
    CHECK(!st_voice_position(&voice,NAN)&&!st_voice_position(&voice,1.01));
    dna.rate=48000;dna.window=1024;dna.hop=256;dna.base_hz=20;dna.harmonics=1;
    CHECK(sa_bank_init(&bank,models,1,0));config.startup_profile=&profile;config.scene_mode=AD_SCENE_STEREO_BED;c.mix.startup_gain=.7;
    for(i=0;i<3;++i){config.channels=i==1?12:2;CHECK(ad_render_init(render+i,engine+i,&config,&c));}
    for(i=0;i<render[0].startup.cloud.count;++i)initial_hz[i]=render[0].startup.cloud.oscillator[i].hz;
    for(n=0;n<800;++n) {
        c.drive.ignition=(n>=10&&n<280)||n>=400;c.drive.start_id=n>=430?2:n>=30?1:0;
        for(i=0;i<3;++i) {
            AdCapture cap={0};cap.startup=startup[i];CHECK(ad_render_set(render+i,&c));
            if(i!=2)CHECK(ad_render_process(render+i,out[i],N,&cap));
            else for(k=0;k<N;++k){cap.startup=startup[i]+2*k;CHECK(ad_render_process(render+i,out[i]+2*k,1,&cap));}
            CHECK(!memcmp(&engine[0].drive,&engine[i].drive,sizeof engine[0].drive));
        }
        CHECK(!memcmp(out[0],out[2],2*N*sizeof(float))&&!memcmp(startup[0],startup[1],2*N*sizeof(float)));
        for(k=0;k<N;++k){CHECK(out[0][2*k]==out[1][12*k]&&out[0][2*k+1]==out[1][12*k+1]);
            CHECK(fabs(out[0][2*k]-.2*startup[0][2*k])<2e-8&&fabs(out[0][2*k+1]-.2*startup[0][2*k+1])<2e-8);
            for(i=2;i<12;++i)CHECK(out[1][12*k+i]==0);}
        CHECK(!memcmp(&render[0].startup.cloud,&render[2].startup.cloud,sizeof voice.cloud));
        if(n==150)CHECK(render[0].startup.envelope<.01);
    }
    CHECK(engine[0].drive.start_events==2);
    for(i=0;i<render[0].startup.cloud.count;++i)CHECK(render[0].startup.cloud.oscillator[i].hz==initial_hz[i]);
    config.startup_profile=NULL;CHECK(!ad_render_init(render,engine,&config,&c));
    puts("PASS PSD endpoints/complex sign, no pitch modulation, two driver starts, source/layout/chunk isolation, no duplicate bed");return 0;
}
