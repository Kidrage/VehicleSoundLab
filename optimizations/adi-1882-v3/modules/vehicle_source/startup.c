#include "internal.h"
#include "drive/lifecycle.h"
int vs_engine_startup_set(VsEngine *s,const VsStartupResponse *p) {
    if(!s||!vsl_lifecycle_profile_valid(p)||s->generator.frame||s->event_runtime->frame||
       s->event_runtime->started||s->event_control.count||s->generator.owner->drive.lifecycle!=VSL_OFF)return 0;
    s->generator.owner->drive.lifecycle_response=*p;s->generator.owner->drive.lifecycle_override=1;return 1;
}
int vs_engine_startup_get(const VsEngine *s,VsStartupResponse *p) {
    if(!s||!p)return 0;
    *p=*vsl_drive_lifecycle_profile(&s->generator.owner->drive,s->generator.config.profile);return 1;
}
