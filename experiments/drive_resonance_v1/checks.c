#include "drive_resonance/voice.h"
#include "resonant_detail_io/profile.h"
#include "atlas_take/player.h"
#include "atlas_take_io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"resonant drive line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define PI 3.14159265358979323846
static SdProfile models[2];static SaBank bank;static DrsBank detail,saved_bank;
static RdtProfile profile[2];static DrsVoice on,off,saved_voice;static RdtVoice oracle;
static AmRender a,b;static VslEngine ea,eb;static AtPlayer player;
static float xa[30000*2],xb[30000*2],wide[512*12],raw[1024],dna[1024],residual[1024],body[1024],events[512];
static float aux[512*VSL_OBJECTS],start[1024],catching[1024],resonant[1024];
static int kernel(void) {
    const SdProfile *p[2]={models,models+1};const RdtProfile *q[2]={profile,NULL};SaVoice carrier={0};unsigned i,n;
    for(i=0;i<2;++i) {
        RdtProfile *m=profile+i;RdtBand *v=m->band;
        m->rate=48000;m->count=1;m->base_hz=models[i].base_hz;m->warmup_frames=67;
        v->low_hz=400;v->high_hz=2000;v->order=1;v->a[0]=1;v->a[1]=-.5;v->sigma=.01;
        v->sections=1;v->sos[0][0]=.2;v->sos[0][3]=1;v->sos[0][4]=-.8;v->gain=.7;v->right_over_left=.8;
        v->envelope_order=1;v->beta[0]=.2;v->beta[1]=.1;
    }
    CHECK(sa_bank_init(&bank,p,2,0)&&drs_bank_init(&detail,&bank,q));
    saved_bank=detail;profile[0].base_hz+=1;CHECK(!drs_bank_init(&detail,&bank,q)&&!memcmp(&detail,&saved_bank,sizeof detail));profile[0].base_hz-=1;
    CHECK(drs_voice_init(&on,&detail,&bank,8121907,1)&&drs_voice_init(&off,&detail,&bank,8121907,0));
    CHECK(rdt_voice_init(&oracle,profile,8121907));
    for(n=0;n<profile[0].warmup_frames;++n){double phase=fmod(((double)n-profile[0].warmup_frames)*profile[0].base_hz/48000,1),v[2];if(phase<0)phase+=1;CHECK(rdt_voice_tick(&oracle,phase,v,NULL));}
    carrier.bank=&bank;carrier.root_hz=models[0].base_hz;
    for(n=0;n<1024;++n) {
        DrsFrame x,y;double sample[2],phase=fmod(.23+n*carrier.root_hz/48000,1);
        CHECK(drs_voice_tick(&on,&carrier,phase*2*PI,&x)&&drs_voice_tick(&off,&carrier,phase*2*PI,&y));
        CHECK(rdt_voice_tick(&oracle,phase,sample,NULL));
        CHECK(fabs(x.raw[0]-sample[0])<1e-15&&x.support==1&&x.raw[0]==y.raw[0]&&x.raw[1]==y.raw[1]);
        CHECK(y.output[0]==0&&y.output[1]==0&&x.output[0]==x.raw[0]);
    }
    saved_voice=on;CHECK(!drs_voice_set(&on,NAN)&&!memcmp(&on,&saved_voice,sizeof on));
    carrier.root_hz=models[1].base_hz;carrier.lower=carrier.upper=1;
    {DrsFrame x;uint64_t before=on.voice[0].frame;CHECK(drs_voice_tick(&on,&carrier,.4,&x)&&x.support==0&&x.raw[0]==0&&on.voice[0].frame==before+1);}
    /* A second, distinct synthetic anchor verifies reuse and aligned phase input. */
    q[1]=profile+1;profile[1].band[0].a[1]=-.8;CHECK(drs_bank_init(&detail,&bank,q));bank.offset[1]=.31;
    CHECK(drs_voice_init(&on,&detail,&bank,8121907,1));
    CHECK(rdt_voice_init(&oracle,profile+1,8121907^UINT64_C(0x9e3779b97f4a7c15)));
    for(n=0;n<profile[1].warmup_frames;++n){double ph=fmod(((double)n-profile[1].warmup_frames)*profile[1].base_hz/48000+.31/(2*PI),1),z[2];if(ph<0)ph+=1;CHECK(rdt_voice_tick(&oracle,ph,z,NULL));}
    {DrsFrame x;double z[2];CHECK(drs_voice_tick(&on,&carrier,.4,&x));CHECK(rdt_voice_tick(&oracle,(.4+.31)/(2*PI),z,NULL));CHECK(fabs(x.raw[0]-z[0])<1e-15&&x.support==1);}
    bank.offset[1]=-.31;CHECK(drs_voice_init(&on,&detail,&bank,8121907,1));
    {DrsFrame x;CHECK(drs_voice_tick(&on,&carrier,nextafter(.31,0),&x));CHECK(isfinite(x.raw[0])&&on.frame==1);}
    return 0;
}
static int driving_and_take(void) {
    const SdProfile *p[2]={models,models+1};const RdtProfile *q[2]={profile,NULL};AdConfig cfg={0};AdControl c={0},bad;
    AdCapture capture={0};AtTake take={0},loaded={0};unsigned at,n;uint64_t sh=AT_HASH_INITIAL,ah=AT_HASH_INITIAL;double energy=0;
    unsigned char *bytes=NULL;size_t length=0;
    CHECK(rdt_profile_load("voices/resonant_detail_c_v1/idle_add.rdetail",profile));
    CHECK(sa_bank_init(&bank,p,2,32)&&drs_bank_init(&detail,&bank,q));
    cfg.bank=&bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=2;cfg.root_per_rpm=1./120;cfg.scene_mode=AD_SCENE_STEREO_BED;
    c.drive.mode=VSL_BENCH;c.drive.ignition=1;c.drive.start_id=1;c.drive.gear=1;c.drive.rpm=profile[0].base_hz*120;c.drive.load=.6;
    c.mix.gain=.25;c.mix.detail=1;c.mix.width=1;
    CHECK(am_render_init(&a,&ea,&cfg,&c));cfg.resonant_bank=&detail;CHECK(am_render_init(&b,&eb,&cfg,&c));
    CHECK(am_render_process(&a,xa,30000,0,NULL)&&am_render_process(&b,xb,30000,0,NULL));CHECK(!memcmp(xa,xb,sizeof xa));
    CHECK(a.drive.dna.phase==b.drive.dna.phase&&ea.drive.rpm==eb.drive.rpm&&ea.drive.shift_events==eb.drive.shift_events);
    CHECK(b.drive.resonant.frame==30000&&b.drive.resonant.voice[0].frame==30000+profile[0].warmup_frames);
    cfg.resonant_bank=NULL;bad=c;bad.mix.resonant_gain=.5;CHECK(!ad_render_set(&a.drive,&bad));cfg.resonant_bank=&detail;c.mix.resonant_gain=.7;
    CHECK(at_take_allocate(&take,16)&&at_take_begin(&take,&cfg,&c));
    CHECK(am_render_init(&a,&ea,&take.assets->config,&c)&&at_take_event(&take,0,&c));
    capture.dna_raw=raw;capture.dna=dna;capture.residual=residual;capture.body=body;capture.events=events;
    capture.aux_objects=aux;capture.startup=start;capture.catch_bloom=catching;capture.resonant=resonant;
    for(at=0;at<30000;at+=n) {
        n=30000-at;if(n>257)n=257;
        if(at<3001&&at+n>3001)n=3001-at;if(at<7777&&at+n>7777)n=7777-at;
        if(at==3001){c.drive.rpm=4000;CHECK(at_take_event(&take,at,&c)&&am_render_set(&a,&c));}
        if(at==7777){c.drive.rpm=profile[0].base_hz*120;c.mix.resonant_gain=1;CHECK(at_take_event(&take,at,&c)&&am_render_set(&a,&c));}
        CHECK(am_render_process(&a,xa+2*at,n,0,&capture));
        for(unsigned j=0;j<n*2;++j)energy+=resonant[j]*resonant[j];
        sh=at_hash_sources(sh,&capture,n);ah=at_hash_samples(ah,xa+2*at,n*2);CHECK(at_take_commit(&take,n,ah,sh));
    }
    CHECK(energy>1e-7);at_take_finish(&take);CHECK(at_take_encode(&take,&bytes,&length));CHECK(bytes[8]==9&&bytes[76]==30);
    CHECK(at_take_decode(&loaded,bytes,length));CHECK(loaded.assets->config.resonant_bank==&loaded.assets->resonant);
    CHECK(loaded.assets->resonant.enabled[0]&&!loaded.assets->resonant.enabled[1]);
    memset(&detail,0,sizeof detail);memset(profile,0,sizeof profile);memset(models,0,sizeof models);memset(&bank,0,sizeof bank);
    CHECK(at_player_init(&player,&eb,&loaded,2));
    for(at=0;at<30000;at+=n){n=30000-at;if(n>347)n=347;CHECK(at_player_process(&player,xb+at*2,n,NULL)==n);}
    CHECK(at_player_verified(&player)&&!memcmp(xa,xb,sizeof xa));
    CHECK(at_player_init(&player,&eb,&loaded,12));while(!at_player_complete(&player))CHECK(at_player_process(&player,wide,512,NULL)>0);
    CHECK(at_player_verified(&player)&&player.source_hash==sh);
    free(bytes);at_take_free(&take);at_take_free(&loaded);return 0;
}
int main(void) {
    CHECK(sd_profile_load("voices/exterior_anchors_v1/A Stationary Low.model",models));
    CHECK(sd_profile_load("voices/exterior_anchors_v1/A Stationary Lower Mid.model",models+1));
    CHECK(!kernel());CHECK(!driving_and_take());
    puts("PASS: local support, missing anchors, one supplied phase, mute clocks, driver zero bypass and owned schema9 2/12 replay");return 0;
}
