#include "control.h"
#include <math.h>
static int unit(double x) { return isfinite(x)&&x>=0&&x<=1; }
static int flag(int x) { return x==0||x==1; }
int ad_control_valid(const AdControl *c,int channels) {
    const AdInput *p;
    const AdMix *m;
    if (!c || (channels!=2&&channels!=12)) return 0;
    p=&c->drive;m=&c->mix;
    return p->mode>=VSL_BENCH&&p->mode<=VSL_AUTODRIVE&&flag(p->ignition)&&p->start_id>=0&&
        p->gear>=0&&p->gear<=7&&flag(p->automatic)&&flag(p->backfire)&&
        isfinite(p->rpm)&&p->rpm>=0&&p->rpm<=10000&&isfinite(p->load)&&p->load>=-1&&p->load<=1&&
        unit(p->throttle)&&unit(p->brake)&&unit(m->gain)&&unit(m->detail)&&unit(m->event_gain)&&
        unit(m->width)&&unit(m->room)&&unit(m->perspective)&&unit(m->residual_gain)&&unit(m->body_mix)&&
        unit(m->intake_gain)&&unit(m->mechanical_gain)&&unit(m->air_gain)&&unit(m->road_gain)&&unit(m->wind_gain)&&flag(m->spatial)&&flag(m->propagation)&&
        (channels!=12||m->spatial);
}
void ad_control_apply(VslEngine *e,const AdControl *c) {
    const AdInput *p=&c->drive;
    e->target.drive_mode=p->mode;e->target.ignition=p->ignition;e->target.start_id=p->start_id;
    e->target.gear=p->gear;e->target.auto_gear=p->automatic;e->target.backfire=p->backfire;
    e->target.rpm=p->rpm;e->target.load=p->load;e->target.throttle=p->throttle;e->target.brake=p->brake;
    e->target.width=c->mix.width;e->target.space=c->mix.room;e->target.perspective=c->mix.perspective;
    e->target.propagation=c->mix.propagation;
}
