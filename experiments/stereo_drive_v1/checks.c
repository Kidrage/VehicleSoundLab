#include "drive_resonance/voice.h"
#include "stereo_resonance_io/profile.h"
#include "atlas_take/player.h"
#include "atlas_take_io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"stereo drive line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define PI 3.14159265358979323846
#define FRAMES 96000
static SdProfile model[3];static SaBank bank;static DrsBank detail,saved;
static RdtProfile rdt;static RvsProfile stereo;static DrsVoice on,off;
static RdtVoice ro;static RvsVoice so;static AmRender a,b;static VslEngine ea,eb;
static AtPlayer player;static float xa[FRAMES*2],xb[FRAMES*2],wide[512*12];
static float raw[1024],dna[1024],residual[1024],body[1024],events[512],aux[512*VSL_OBJECTS];
static float startup[1024],catching[1024],resonant[1024];
static double support(double root,double hz) {
    double x=hz/root,u;if(x<=.9||x>=1.1)return 0;
    if(x<.96)u=(x-.9)/.06;else if(x>1.04)u=(1.1-x)/.06;else return 1;
    return u*u*(3-2*u);
}
static int mixed(void) {
    const SdProfile *p[3]={model,model+1,model+2};
    const RdtProfile *r[3]={&rdt,NULL,NULL};const RvsProfile *s[3]={NULL,&stereo,NULL};
    SaVoice carrier={0};RvsBand *m=stereo.band;RdtBand *q=rdt.band;unsigned n,i;
    for(i=0;i<3;++i){model[i].rate=48000;model[i].window=1024;model[i].hop=256;
        model[i].harmonics=2;model[i].base_hz=30+3*i;model[i].harmonic[0].mean[0]=.1;model[i].harmonic[0].mean[2]=.07;}
    rdt.rate=48000;rdt.count=1;rdt.base_hz=30;rdt.warmup_frames=0;
    q->order=1;q->a[0]=1;q->a[1]=-.4;q->sigma=.01;q->gain=.5;q->right_over_left=.7;
    q->low_hz=400;q->high_hz=800;q->sections=1;q->sos[0][0]=q->sos[0][3]=1;
    q->envelope_order=1;q->beta[0]=.12;
    stereo.rate=48000;stereo.count=1;stereo.base_hz=33;stereo.warmup_frames=73;
    m->order=1;m->low_hz=400;m->high_hz=800;m->gain=.8;
    m->a[0][0][0]=m->a[0][1][1]=.25;m->a[0][0][1]=.1;m->a[0][1][0]=-.1;
    m->noise[0][0]=.01;m->noise[1][0]=.004;m->noise[1][1]=.015;
    m->certificate[0][0]=m->certificate[1][1]=1;
    m->post.sections=1;memcpy(m->post.sos[0],(double[6]){.4,-.1,.03,1,-.3,.08},6*sizeof(double));
    CHECK(sa_bank_init(&bank,p,3,0)&&drs_bank_init_mixed(&detail,&bank,r,s));
    CHECK(detail.kind[0]==DRS_RDT&&detail.kind[1]==DRS_STEREO&&!detail.enabled[2]);
    saved=detail;s[0]=&stereo;CHECK(!drs_bank_init_mixed(&detail,&bank,r,s)&&!memcmp(&detail,&saved,sizeof detail));s[0]=NULL;
    stereo.band[0].certificate[0][0]=-1;
    CHECK(!drs_bank_init_mixed(&detail,&bank,r,s)&&!memcmp(&detail,&saved,sizeof detail));stereo.band[0].certificate[0][0]=1;
    CHECK(drs_voice_init(&on,&detail,&bank,619,1)&&drs_voice_init(&off,&detail,&bank,619,0));
    CHECK(rdt_voice_init(&ro,&rdt,619)&&rvs_voice_init(&so,&stereo,619^UINT64_C(0x9e3779b97f4a7c15),1));
    carrier.bank=&bank;
    for(n=0;n<2048;++n) {
        DrsFrame x,y;double hz=n<1024?31.5:36,z[2],v[2],phase=fmod(.31+n*.004,2*PI),weight[2];
        carrier.root_hz=hz;carrier.lower=n<1024?0:2;carrier.upper=n<1024?1:2;carrier.blend=n<1024?.5:0;
        CHECK(drs_voice_tick(&on,&carrier,phase,&x)&&drs_voice_tick(&off,&carrier,phase,&y));
        CHECK(rdt_voice_tick(&ro,phase/(2*PI),z,NULL)&&rvs_voice_tick(&so,v,NULL));
        weight[0]=n<1024?sqrt(.5)*support(30,hz):0;weight[1]=n<1024?sqrt(.5)*support(33,hz):0;
        CHECK(fabs(x.support-weight[0]*weight[0]-weight[1]*weight[1])<1e-14);
        for(i=0;i<2;++i){CHECK(fabs(x.raw[i]-z[i]*weight[0]-v[i]*weight[1])<1e-15);
            CHECK(x.raw[i]==y.raw[i]&&y.output[i]==0);}
    }
    CHECK(on.stereo[1].frame==2048&&on.voice[0].frame==2048);
    CHECK(!memcmp(on.stereo[1].history,off.stereo[1].history,sizeof so.history));
    CHECK(!memcmp(on.stereo[1].excitation,off.stereo[1].excitation,sizeof so.excitation));
    /* Mixed owned serialization must retain both kinds, the gap and certificate. */
    {
        AdConfig cfg={0};AdControl c={0};AtTake t={0},u={0};unsigned char *bytes=NULL;size_t length=0;
        cfg.bank=&bank;cfg.resonant_bank=&detail;cfg.seed=619;cfg.profile=VSL_V10;cfg.channels=2;cfg.root_per_rpm=1./120;
        c.drive.mode=VSL_BENCH;c.drive.rpm=3600;c.mix.gain=.25;c.mix.detail=1;c.mix.width=1;
        AdCapture cap={0};
        cap.dna_raw=raw;cap.dna=dna;cap.residual=residual;cap.body=body;cap.events=events;
        cap.aux_objects=aux;cap.startup=startup;cap.catch_bloom=catching;cap.resonant=resonant;
        CHECK(at_take_allocate(&t,2)&&at_take_begin(&t,&cfg,&c)&&at_take_event(&t,0,&c));
        CHECK(am_render_init(&a,&ea,&t.assets->config,&c)&&am_render_process(&a,xa,1,0,&cap));
        CHECK(at_take_commit(&t,1,at_hash_samples(AT_HASH_INITIAL,xa,2),at_hash_sources(AT_HASH_INITIAL,&cap,1)));
        at_take_finish(&t);CHECK(at_take_encode(&t,&bytes,&length));
        CHECK(at_take_decode(&u,bytes,length)&&u.assets->resonant.kind[0]==DRS_RDT&&u.assets->resonant.kind[1]==DRS_STEREO);
        CHECK(!u.assets->resonant.enabled[2]&&!memcmp(&u.assets->resonant.stereo[1],&stereo,sizeof stereo));
        free(bytes);at_take_free(&t);at_take_free(&u);
    }
    return 0;
}
static int real_take(void) {
    const SdProfile *p[1]={model};const RvsProfile *s[1]={&stereo};
    AdConfig cfg={0};AdControl c={0};AtTake t={0},u={0};AdCapture cap={0};
    unsigned n,at;unsigned char *bytes=NULL;size_t length=0;double power=0;
    uint64_t sh=AT_HASH_INITIAL,ah=AT_HASH_INITIAL;
    CHECK(sd_profile_load("voices/startup_settle_v1/A start cabin settle.model",model));
    CHECK(rvs_profile_load("voices/stereo_resonance_v1/A cabin settle.sres",&stereo));
    CHECK(sa_bank_init(&bank,p,1,32)&&drs_bank_init_stereo(&detail,&bank,s));
    cfg.bank=&bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=2;
    cfg.root_per_rpm=model[0].base_hz/850;cfg.scene_mode=AD_SCENE_STEREO_BED;
    c.drive.mode=VSL_BENCH;c.drive.ignition=1;c.drive.start_id=1;c.drive.rpm=850;c.drive.load=.6;
    c.mix.gain=.25;c.mix.detail=1;c.mix.width=1;
    CHECK(am_render_init(&a,&ea,&cfg,&c));cfg.resonant_bank=&detail;CHECK(am_render_init(&b,&eb,&cfg,&c));
    CHECK(am_render_process(&a,xa,FRAMES,0,NULL)&&am_render_process(&b,xb,FRAMES,0,NULL));
    CHECK(!memcmp(xa,xb,sizeof xa)&&a.drive.dna.phase==b.drive.dna.phase&&ea.drive.rpm==eb.drive.rpm);
    CHECK(b.drive.resonant.stereo[0].frame==FRAMES);
    c.mix.resonant_gain=.7;CHECK(at_take_allocate(&t,8)&&at_take_begin(&t,&cfg,&c));
    CHECK(am_render_init(&a,&ea,&t.assets->config,&c)&&at_take_event(&t,0,&c));
    cap.dna_raw=raw;cap.dna=dna;cap.residual=residual;cap.body=body;cap.events=events;
    cap.aux_objects=aux;cap.startup=startup;cap.catch_bloom=catching;cap.resonant=resonant;
    for(at=0;at<FRAMES;at+=n) {
        n=FRAMES-at;if(n>257)n=257;if(at<30000&&at+n>30000)n=30000-at;if(at<60000&&at+n>60000)n=60000-at;
        if(at==30000||at==60000){c.drive.rpm=at==30000?6000:850;CHECK(at_take_event(&t,at,&c)&&am_render_set(&a,&c));}
        CHECK(am_render_process(&a,xa+2*at,n,0,&cap));
        for(unsigned j=0;j<2*n;++j)power+=(double)resonant[j]*resonant[j];
        sh=at_hash_sources(sh,&cap,n);ah=at_hash_samples(ah,xa+2*at,2*n);CHECK(at_take_commit(&t,n,ah,sh));
    }
    CHECK(power>1e-8);at_take_finish(&t);CHECK(at_take_encode(&t,&bytes,&length)&&bytes[8]==10&&bytes[76]==32);
    CHECK(at_take_decode(&u,bytes,length));
    memset(model,0,sizeof model);memset(&bank,0,sizeof bank);memset(&detail,0,sizeof detail);memset(&stereo,0,sizeof stereo);
    CHECK(at_player_init(&player,&eb,&u,2));
    for(at=0;at<FRAMES;at+=n){n=FRAMES-at;if(n>347)n=347;CHECK(at_player_process(&player,xb+2*at,n,NULL)==n);}
    CHECK(at_player_verified(&player)&&!memcmp(xa,xb,sizeof xa));
    CHECK(at_player_init(&player,&eb,&u,12));
    for(at=0;at<FRAMES;at+=n){n=FRAMES-at;if(n>512)n=512;CHECK(at_player_process(&player,wide,n,NULL)==n);
        for(unsigned j=0;j<n;++j){CHECK(wide[12*j]==xa[2*(at+j)]&&wide[12*j+1]==xa[2*(at+j)+1]);
            for(unsigned k=2;k<12;++k)CHECK(wide[12*j+k]==0);}}
    CHECK(at_player_verified(&player)&&player.source_hash==sh);
    free(bytes);at_take_free(&t);at_take_free(&u);return 0;
}
int main(void) {
    CHECK(!mixed()&&!real_take());
    puts("PASS: mixed kernels/gaps/transaction/stability, oracle/muted clocks, zero driver and owned stereo schema10 2/12 replay");return 0;
}
