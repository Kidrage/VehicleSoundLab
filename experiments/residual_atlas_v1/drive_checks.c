#include "atlas_drive/render.h"
#include "core/engine.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"layer drive line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static SdProfile profiles[2];static SaBank dna_bank;static RaBank residual_bank;
static VslEngine ea,eb,ec;static AdRender a,b,c;
static float x[480],y[480],z[2880],raw_a[480],raw_b[480],raw_c[480],r1[480],r2[480],layer[480],objects[2400],r_objects[2400];
int main(void) {
    const SdProfile *ptr[2]={&profiles[0],&profiles[1]};double roots[2]={20,80};
    SrProfile s={48000,1,32,{{1200,8000,{.0001,.0002},{.6,.2}}}};const SrProfile *sp[2]={&s,&s};
    AdConfig config={&dna_bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl ctl={{VSL_BENCH,1,1,1,0,1,6000,.8,0,0},{.25,1,0,.7,0,0,0,0}};
    AdCapture ca={0},cb={0},cc={0};unsigned n,j,h;int different=0;
    for(n=0;n<2;++n) {
        SdProfile *p=&profiles[n];p->rate=48000;p->window=1024;p->hop=256;p->base_hz=roots[n];p->harmonics=8;
        for(h=0;h<8;++h){p->harmonic[h].mean[0]=.05/(h+1);p->harmonic[h].mean[2]=.04/(h+1);}
    }
    CHECK(sa_bank_init(&dna_bank,ptr,2,0)&&ra_bank_init(&residual_bank,sp,roots,2));
    CHECK(ad_render_init(&a,&ea,&config,&ctl));
    config.residual_bank=&residual_bank;CHECK(ad_render_init(&b,&eb,&config,&ctl));
    config.channels=12;ctl.mix.spatial=1;ctl.mix.residual_gain=1;
    CHECK(ad_render_init(&c,&ec,&config,&ctl));
    ca.dna_raw=raw_a;cb.dna_raw=raw_b;cb.residual_raw=r1;
    cc.dna_raw=raw_c;cc.residual_raw=r2;cc.residual=layer;cc.objects=objects;cc.residual_objects=r_objects;
    for(n=0;n<600;++n) {
        CHECK(ad_render_process(&a,x,240,&ca)&&ad_render_process(&b,y,240,&cb)&&ad_render_process(&c,z,240,&cc));
        CHECK(!memcmp(x,y,sizeof x)&&!memcmp(raw_a,raw_b,sizeof raw_a)&&!memcmp(raw_a,raw_c,sizeof raw_a));
        CHECK(!memcmp(r1,r2,sizeof r1)&&!memcmp(&ea.drive,&eb.drive,sizeof ea.drive)&&!memcmp(&ea.drive,&ec.drive,sizeof ea.drive));
        for(j=0;j<480;++j){CHECK(isfinite(r1[j]));different|=fabs(layer[j])>1e-7;}
        for(j=0;j<240;++j) {
            CHECK(r_objects[j*10]==r_objects[j*10+1]);
            for(h=2;h<10;++h)CHECK(r_objects[j*10+h]==0);
        }
    }
    CHECK(different&&b.residual.frame==b.frame&&c.residual.frame==c.frame);
    ctl.mix.spatial=0;ctl.mix.residual_gain=.7;
    CHECK(!ad_render_set(&a,&ctl)&&ad_render_set(&b,&ctl));
    ctl.drive.ignition=0;ctl.drive.rpm=0;ctl.mix.spatial=1;CHECK(ad_render_set(&c,&ctl));
    for(n=0;n<600;++n)CHECK(ad_render_process(&c,z,240,&cc));
    for(j=0;j<480;++j)CHECK(fabs(layer[j])<1e-7);
    puts("PASS: residual zero bypass, source/layout/controller isolation, object stems and ignition release");return 0;
}
