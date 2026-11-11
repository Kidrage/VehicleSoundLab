#include "atlas_drive/render.h"
#include "core/engine.h"
#include "drive/drive.h"
#include "drive/scenarios.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"drive check line%d: %s\n",__LINE__,#x);return 1; } } while(0)
static SdProfile low,high;
static SaBank bank;
static AdRender a,b,surround;
static VslEngine ea,eb,ec;
static float x[240*2],y[240*2],z[240*12],raw_a[240*2],raw_b[240*2],raw_c[240*2];
static float objects[240*VSL_OBJECTS];
static AdTelemetry trace[240];

static void scenario(AdControl *c,VslParams *p,int id,double t) {
    vsl_scenario_apply(id,t,p);
    c->drive.mode=p->drive_mode;c->drive.ignition=p->ignition;c->drive.start_id=p->start_id;
    c->drive.gear=p->gear;c->drive.automatic=p->auto_gear;c->drive.backfire=p->backfire;
    c->drive.rpm=p->rpm;c->drive.load=p->load;c->drive.throttle=p->throttle;c->drive.brake=p->brake;
}
int main(void) {
    const SdProfile *models[2]={&low,&high};
    AdConfig config={&bank,48271,VSL_V10,2,1.0/120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl c={{VSL_AUTODRIVE,1,1,1,1,1,1200,.5,0,0},{.5,1,0,.7,0,0,0,0}}, cb;
    AdCapture ca={0},capb={0},capc={0};
    VslDrive reference;
    VslParams p=vsl_default_params(VSL_V10);
    unsigned block,j,shifts=0,overruns=0,seen=0;
    double peak=0;
    low.rate=48000;low.window=1024;low.hop=256;low.harmonics=8;low.base_hz=60;
    low.harmonic[0].mean[0]=.12;low.harmonic[0].mean[2]=.08;
    low.harmonic[4].mean[0]=.1;low.harmonic[4].mean[3]=.07;
    high=low;high.base_hz=65;high.harmonic[0].mean[0]=.09;
    CHECK(sa_bank_init(&bank,models,2,8));
    CHECK(ad_render_init(&a,&ea,&config,&c));
    CHECK(ad_render_init(&b,&eb,&config,&c));
    config.channels=12;cb=c;cb.mix.spatial=1;cb.mix.gain=0;
    CHECK(ad_render_init(&surround,&ec,&config,&cb));
    vsl_drive_reset(&reference,VSL_V10);
    ca.dna_raw=raw_a;ca.telemetry=trace;ca.objects=objects;
    capb.dna_raw=raw_b;capc.dna_raw=raw_c;
    for (block=0;block<6000;++block) {
        scenario(&c,&p,VSL_SCENARIO_AUTO,block*.005);
        cb=c;cb.mix.gain=0;cb.mix.spatial=1;cb.mix.room=.5;
        CHECK(ad_render_set(&a,&c)&&ad_render_set(&b,&c)&&ad_render_set(&surround,&cb));
        vsl_drive_step(&reference,&ea.target,.005);
        CHECK(ad_render_process(&a,x,240,&ca));
        CHECK(ad_render_process(&b,y,37,&capb));
        capb.dna_raw=raw_b+74;CHECK(ad_render_process(&b,y+74,203,&capb));capb.dna_raw=raw_b;
        CHECK(ad_render_process(&surround,z,240,&capc));
        CHECK(!memcmp(&reference,&ea.drive,sizeof reference));
        CHECK(!memcmp(x,y,sizeof x)&&!memcmp(raw_a,raw_b,sizeof raw_a)&&!memcmp(raw_a,raw_c,sizeof raw_a));
        CHECK(a.frame==ea.frame&&a.frame==a.dna.frame);
        shifts=ea.drive.shift_events;overruns=ea.drive.overrun_events;
        if (ea.drive.lifecycle==VSL_RUNNING) seen|=1u<<ea.drive.operating;
        for (j=0;j<240;++j) {
            CHECK(trace[j].frame==(uint64_t)block*240+j&&isfinite(trace[j].root_hz));
            if (trace[j].coverage<0) seen|=1u<<16;
            if (trace[j].coverage==0) seen|=1u<<17;
            CHECK(objects[j*VSL_OBJECTS]==objects[j*VSL_OBJECTS+1]);
            /* No legacy tonal engine is secretly rendered underneath. */
            CHECK(objects[j*VSL_OBJECTS+VSL_INTAKE]==0&&objects[j*VSL_OBJECTS+VSL_BODY]==0);
        }
        for (j=0;j<480;++j) { CHECK(isfinite(x[j]));peak=fmax(peak,fabs(x[j])); }
        for (j=0;j<240*12;++j) CHECK(z[j]==0);
    }
    CHECK(shifts>=2&&overruns>=1&&peak>.001&&peak<.95);
    CHECK(seen&(1u<<VSL_SHIFT_CUT));CHECK(seen&(1u<<VSL_OVERRUN));
    CHECK((seen&(1u<<16))&&(seen&(1u<<17)));
    CHECK(ea.dna.pitch_phase==0&&ea.pad.phase[0]==0&&ea.high_orders.active==0);
    cb=c;cb.mix.detail=NAN;
    CHECK(!ad_render_set(&a,&cb)&&a.target.mix.detail==c.mix.detail);
    CHECK(!ad_render_process(&a,NULL,1,NULL)&&ad_render_process(&a,NULL,0,NULL));
    c.drive.ignition=0;
    for (block=0;block<800;++block) { CHECK(ad_render_set(&a,&c));CHECK(ad_render_process(&a,x,240,NULL)); }
    CHECK(ea.drive.lifecycle==VSL_OFF&&a.envelope<1e-8);
    printf("atlas driving checks: shifts%u overruns%u peak%.8g; reference controller / chunk / routing / mute passed\n",shifts,overruns,peak);
    return 0;
}
