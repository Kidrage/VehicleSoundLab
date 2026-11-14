#include "assets.h"
#include "atlas_drive/render.h"
#include "core/engine.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"local driver check %d: %s\n",__LINE__,#x);return 1;}}while(0)
static LaAssets assets;static AdRender r2,r12;static VslEngine e2,e12;
static float out2[514],out12[3084],raw2[514],raw12[514],layers2[257*LM_SAMPLES],layers12[257*LM_SAMPLES];
int main(int argc,char **argv) {
    AdConfig c={0},wide;AdControl u={0},uw;AdCapture a={0},b={0};unsigned at,n,j,anchors=0;
    double energy=0,maxroot=0;if(argc!=2)return 2;CHECK(la_assets_load(&assets,argv[1]));
    c.bank=&assets.bank;c.seed=23117;c.profile=VSL_V10;c.channels=2;c.root_per_rpm=1./120;
    c.projection=DS_OBSERVE_MID;c.route=DS_ROUTE_PAIR;c.scene_mode=AD_SCENE_STEREO_BED;
    u.drive.mode=VSL_BENCH;u.drive.ignition=u.drive.start_id=1;u.drive.gear=5;
    u.drive.rpm=assets.models[0].base_hz*120;u.drive.load=.7;
    u.mix.gain=.25;u.mix.detail=u.mix.width=1;wide=c;wide.channels=12;uw=u;uw.mix.spatial=1;
    CHECK(ad_render_init(&r2,&e2,&c,&u)&&ad_render_init(&r12,&e12,&wide,&uw));
    a.dna_raw=raw2;a.layers=layers2;b.dna_raw=raw12;b.layers=layers12;
    for(at=0;at<240123;at+=n) {
        n=240123-at>257?257:240123-at;
        for(j=1;j<4;++j)if(at<j*48000&&at+n>j*48000)n=j*48000-at;
        if(at==48000)u.drive.rpm=assets.models[1].base_hz*120;
        if(at==96000){u.drive.rpm=assets.models[2].base_hz*120;u.drive.load=.4;}
        if(at==144000){u.drive.rpm=assets.models[0].base_hz*120;u.drive.load=-.4;}
        uw=u;uw.mix.spatial=1;CHECK(ad_render_set(&r2,&u)&&ad_render_set(&r12,&uw));
        CHECK(ad_render_process(&r2,out2,n,&a)&&ad_render_process(&r12,out12,n,&b));
        CHECK(!memcmp(raw2,raw12,n*2*sizeof(float))&&!memcmp(layers2,layers12,n*LM_SAMPLES*sizeof(float)));
        CHECK(!memcmp(&e2.drive,&e12.drive,sizeof e2.drive)&&!memcmp(&r2.dna,&r12.dna,sizeof r2.dna));
        CHECK(r2.dna.frame==r2.frame&&r2.frame==e2.frame&&r12.frame==e12.frame);
        anchors|=1u<<r2.dna.lower;anchors|=1u<<r2.dna.upper;maxroot=fmax(maxroot,r2.dna.root_hz);
        for(j=0;j<n*2;++j){CHECK(isfinite(out2[j]));energy+=(double)raw2[j]*raw2[j];}
        for(j=0;j<n*12;++j)CHECK(isfinite(out12[j]));
    }
    CHECK(energy>0&&(anchors&7)==7&&maxroot>assets.models[1].base_hz);
    ad_render_dispose(&r2);ad_render_dispose(&r12);
    printf("PASS240123 frames same original controller;2/12 raw+six dry buses+drive/DNA state exact;all3anchors visited;maxroot%.12g\n",maxroot);return 0;
}
