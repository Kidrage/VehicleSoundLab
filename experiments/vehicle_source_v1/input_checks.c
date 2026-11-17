#include "vehicle_source/internal.h"
#include "drive/drive.h"
#include "core/engine.h"
#include "../catalog_drive_v1/models.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"input check line%d: %s\n",__LINE__,#x);return 3;}}while(0)
static float audio[480*2];
int main(void) {
    ViState state={0};ViInput p={VI_EXTERNAL,VI_SPEED|VI_ACCELERATION|VI_SLIP,1,15,2,.4};ViAdopted a;
    VslDrive d;VslParams params=vsl_default_params(VSL_V10);VslKinematics k={15,2,.4};
    DcPreset *preset;VsAssets *assets;VsEngine *engine;VsControl c;VsTelemetry t;VsOutput out={0};
    CHECK(vi_accept(&state,&p,100));CHECK(vi_accept(&state,&p,200));
    a=vi_at(&state,501,400);CHECK(a.stale&&a.value.speed_mps==15&&a.value.tire_slip==0&&a.value.acceleration_mps2==0);
    ++p.sequence;CHECK(vi_accept(&state,&p,501));CHECK(!vi_at(&state,502,400).stale);
    --p.sequence;CHECK(!vi_accept(&state,&p,502));++p.sequence;p.speed_mps=16;CHECK(!vi_accept(&state,&p,502));
    ++p.sequence;CHECK(vi_accept(&state,&p,502));p.speed_mps=NAN;CHECK(!vi_valid(&p));p.speed_mps=15;
    p.valid=VI_SPEED|VI_ACCELERATION;++p.sequence;CHECK(vi_accept(&state,&p,502));CHECK(vi_at(&state,502,400).value.tire_slip==0);
    p.valid=VI_SPEED;CHECK(!vi_valid(&p));p.source=VI_INTERNAL;CHECK(!vi_valid(&p));
    p.valid=VI_SLIP;p.sequence=0;CHECK(vi_accept(&state,&p,503));
    vsl_drive_reset(&d,VSL_V10);params.ignition=params.start_id=1;params.drive_mode=VSL_PEDALS;
    params.gear=1;params.auto_gear=0;params.throttle=.7;params.brake=0;
    for(int j=0;j<1000;++j) {
        vsl_drive_step_kinematic(&d,&params,.005,&k);
        CHECK(d.speed_kph==54&&d.vehicle.acceleration_mps2==2&&d.coupling_audit.steps==0&&!d.vehicle.solver_active);
        CHECK(isfinite(d.rpm)&&d.rpm>=0&&d.rpm<=10000);
    }
    CHECK(d.lifecycle==VSL_RUNNING&&d.operating==VSL_PULL&&d.rpm>1000);
    params.throttle=0;params.brake=1;
    for(int j=0;j<200;++j)vsl_drive_step_kinematic(&d,&params,.005,&k);
    CHECK(d.speed_kph==54&&d.coupling_audit.steps==0&&d.vehicle.acceleration_mps2==2);
    preset=cd_models_load(DC_MOVING);CHECK(preset);assets=vs_assets_from_atlas(dc_preset_config(preset));CHECK(assets);
    {AdControl old=dc_preset_initial(preset);vs_control_from_atlas(&old,&c);}dc_preset_destroy(preset);
    c.ignition=c.start_id=1;c.mode=VS_PEDALS;c.automatic=0;c.gear=1;c.throttle=.8;
    c.input=(ViInput){VI_EXTERNAL,VI_SPEED|VI_ACCELERATION|VI_SLIP,1,15,2,.4};
    engine=vs_engine_create(assets,&c);CHECK(engine);out.monitor=audio;
    for(int j=0;j<140;++j)CHECK(vs_engine_process(engine,&out,480));
    CHECK(vs_engine_telemetry(engine,&t)&&t.input_stale&&t.speed_mps==15&&t.acceleration_mps2==0&&t.tire_slip==0);
    CHECK(engine->owner.drive.throttle<.001&&engine->owner.drive.coupling_audit.steps==0);
    ++c.input.sequence;CHECK(vs_engine_set(engine,&c));CHECK(vs_engine_process(engine,&out,480));
    CHECK(vs_engine_telemetry(engine,&t)&&!t.input_stale&&t.tire_slip==.4&&t.acceleration_mps2==2);
    c.input.source=VI_INTERNAL;c.input.valid=0;c.input.sequence=0;
    CHECK(vs_engine_set(engine,&c));CHECK(vs_engine_process(engine,&out,480));
    CHECK(engine->owner.drive.coupling_audit.steps>0);CHECK(vs_engine_telemetry(engine,&t)&&!t.input_stale&&t.input_source==VI_INTERNAL);
    vs_engine_destroy(engine);vs_assets_destroy(assets);
    puts("PASS external kinematics: no double integration, packet age/order, timeout, recovery and authority switch");return 0;
}
