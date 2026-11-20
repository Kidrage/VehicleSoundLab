#include "dsp/perf.h"
#include "internal.h"
#include "drive/drive.h"
void vs_drive_step(void *state,VslDrive *driver,const VslParams *params,uint64_t frame);
void vs_drive_step_impl(void *state,VslDrive *driver,const VslParams *params,uint64_t frame){
    VsEngine *s=state;VslParams adopted=*params;
    ViAdopted a=vi_at(&s->input,frame,VS_RATE/2);s->input_adopted=a;
    if(a.value.source==VI_EXTERNAL) {
        VslKinematics k={a.value.speed_mps,a.value.acceleration_mps2,a.value.tire_slip};
        adopted.drive_mode=VSL_PEDALS;
        if(a.stale){adopted.throttle=adopted.brake=0;adopted.backfire=0;}
        vsl_drive_step_kinematic(driver,&adopted,.005f,&k);
    } else vsl_drive_step(driver,&adopted,.005f);
    vs_state_observe(s,driver);
    vs_events_observe(s,driver,&adopted,frame);
}
void vs_drive_step(void *state,VslDrive *driver,const VslParams *params,uint64_t frame){vsl_perf_enter(10);vs_drive_step_impl(state,driver,params,frame);vsl_perf_leave();}

