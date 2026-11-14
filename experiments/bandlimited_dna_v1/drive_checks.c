#include "test_models.h"
#include "atlas_drive/render.h"
#include "atlas_take/assets.h"
#include "core/engine.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static SdProfile model[2];static SaBank bank;
static AdRender stereo,wide;static VslEngine es,ew;
static float out2[512*2],out12[512*12],raw2[512*2],raw12[512*2];
static float layers2[512*LM_SAMPLES],layers12[512*LM_SAMPLES];
int main(void) {
    const SdProfile *p[2]={model,model+1};
    AdConfig c={0},cw;AdControl u={0},uw;AdCapture a={0},b={0};
    AtAssets *owned;unsigned at,n,j;double maxroot=0,energy=0;
    bd_model(model,80,288,1);bd_model(model+1,100,288,1);
    CHECK(sa_bank_init_bandlimited(&bank,p,2,8));
    c.bank=&bank;c.seed=23117;c.profile=VSL_V10;c.channels=2;
    c.root_per_rpm=1./100; /* Deliberate synthetic map, not measured RPM. */
    c.projection=DS_OBSERVE_MID;c.route=DS_ROUTE_PAIR;c.scene_mode=AD_SCENE_STEREO_BED;
    u.drive.mode=VSL_BENCH;u.drive.ignition=u.drive.start_id=1;u.drive.gear=1;
    u.drive.rpm=9000;u.drive.load=.7;u.mix.gain=.3;u.mix.detail=1;u.mix.width=1;
    cw=c;cw.channels=12;uw=u;uw.mix.spatial=1;
    CHECK(ad_render_init(&stereo,&es,&c,&u)&&ad_render_init(&wide,&ew,&cw,&uw));
    a.dna_raw=raw2;a.layers=layers2;b.dna_raw=raw12;b.layers=layers12;
    for(at=0;at<144123;at+=n) {
        n=144123-at>257?257:144123-at;
        if(at<48000&&at+n>48000)n=48000-at;
        if(at<96000&&at+n>96000)n=96000-at;
        if(at==48000){u.drive.rpm=10000;u.drive.load=.4;}
        if(at==96000){u.drive.rpm=8500;u.drive.load=-.4;}
        uw=u;uw.mix.spatial=1;
        CHECK(ad_render_set(&stereo,&u)&&ad_render_set(&wide,&uw));
        CHECK(ad_render_process(&stereo,out2,n,&a)&&ad_render_process(&wide,out12,n,&b));
        CHECK(!memcmp(raw2,raw12,n*2*sizeof(float))&&!memcmp(layers2,layers12,n*LM_SAMPLES*sizeof(float)));
        CHECK(!memcmp(&es.drive,&ew.drive,sizeof es.drive));
        CHECK(!memcmp(&stereo.dna,&wide.dna,sizeof stereo.dna));
        maxroot=fmax(maxroot,stereo.dna.root_hz);
        for(j=0;j<n*2;++j){CHECK(isfinite(out2[j]));energy+=(double)raw2[j]*raw2[j];}
        for(j=0;j<n*12;++j)CHECK(isfinite(out12[j]));
    }
    CHECK(maxroot>90&&maxroot<=100&&energy>0);
    /* Explicit boundary: schema10 owned loading retains its legacy validator.
       A direct high-anchor engine test does not prove take/UI support. */
    owned=calloc(1,sizeof *owned);CHECK(owned);CHECK(!at_assets_copy(owned,&c));free(owned);
    ad_render_dispose(&stereo);ad_render_dispose(&wide);
    printf("PASS same existing driver/high anchors/2-12 raw and six dry buses exact; max engineering root %.12g Hz; high-root owned copy still rejected\n",maxroot);
    return 0;
}
