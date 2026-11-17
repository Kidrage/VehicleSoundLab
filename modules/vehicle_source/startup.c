#include "internal.h"
#include "drive/lifecycle.h"
int vs_engine_startup_set(VsEngine *s,const VsStartupResponse *p) {
    if(!s||!vsl_lifecycle_profile_valid(p)||s->generator.frame||s->event_pool.frame||
       s->event_pool.started||s->event_control.count||s->owner.drive.lifecycle!=VSL_OFF)return 0;
    s->owner.drive.lifecycle_response=*p;s->owner.drive.lifecycle_override=1;return 1;
}
int vs_engine_startup_get(const VsEngine *s,VsStartupResponse *p) {
    if(!s||!p)return 0;
    *p=*vsl_drive_lifecycle_profile(&s->owner.drive,s->generator.config.profile);return 1;
}
