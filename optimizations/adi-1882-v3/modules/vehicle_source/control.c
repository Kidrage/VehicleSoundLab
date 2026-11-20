#include "internal.h"
#include <string.h>
void vs_control_from_atlas(const AdControl *a,VsControl *v) {
    if(!a||!v)return;
    memset(v,0,sizeof *v);
    v->mode=a->drive.mode;v->ignition=a->drive.ignition;v->start_id=a->drive.start_id;
    v->gear=a->drive.gear;v->automatic=a->drive.automatic;v->backfire=a->drive.backfire;
    v->rpm=a->drive.rpm;v->load=a->drive.load;v->throttle=a->drive.throttle;v->brake=a->drive.brake;
    v->gain=a->mix.gain;v->detail=a->mix.detail;v->legacy_event_gain=a->mix.event_gain;
    v->low_mix=a->mix.body_mix;v->coherent_low_gain=a->mix.coherent_low_gain;
    v->resonant_gain=a->mix.resonant_gain;v->residual_gain=a->mix.residual_gain;
    v->intake_gain=a->mix.intake_gain;v->mechanical_gain=a->mix.mechanical_gain;
    v->air_gain=a->mix.air_gain;v->road_gain=a->mix.road_gain;v->wind_gain=a->mix.wind_gain;
    v->startup_gain=a->mix.startup_gain;v->catch_gain=a->mix.catch_gain;
    v->idle_mix=a->mix.idle_mix;v->idle_motion=a->mix.idle_motion;v->idle_detail=a->mix.idle_detail;
    v->events=ec_default();
    v->dna=dch_default();
}
void vs_control_to_atlas(const VsControl *v,AdControl *a) {
    memset(a,0,sizeof *a);
    a->drive.mode=v->mode;a->drive.ignition=v->ignition;a->drive.start_id=v->start_id;
    a->drive.gear=v->gear;a->drive.automatic=v->automatic;a->drive.backfire=v->backfire;
    a->drive.rpm=v->rpm;a->drive.load=v->load;a->drive.throttle=v->throttle;a->drive.brake=v->brake;
    a->mix.gain=v->gain;a->mix.detail=v->detail;a->mix.event_gain=v->legacy_event_gain;
    a->mix.body_mix=v->low_mix;a->mix.coherent_low_gain=v->coherent_low_gain;
    a->mix.resonant_gain=v->resonant_gain;a->mix.residual_gain=v->residual_gain;
    a->mix.intake_gain=v->intake_gain;a->mix.mechanical_gain=v->mechanical_gain;
    a->mix.air_gain=v->air_gain;a->mix.road_gain=v->road_gain;a->mix.wind_gain=v->wind_gain;
    a->mix.startup_gain=v->startup_gain;a->mix.catch_gain=v->catch_gain;
    a->mix.idle_mix=v->idle_mix;a->mix.idle_motion=v->idle_motion;a->mix.idle_detail=v->idle_detail;
    if(v->dna_unified)a->mix.idle_mix=a->mix.idle_motion=a->mix.idle_detail=0;
    /* No spatial controls in the independent source interface. */
    a->mix.width=1;
    if(v->events.enabled) {
        /* New event bank replaces the old combined starter/pop/texture path. */
        a->mix.event_gain=0;a->mix.startup_gain=0;a->mix.catch_gain=0;
    }
}
