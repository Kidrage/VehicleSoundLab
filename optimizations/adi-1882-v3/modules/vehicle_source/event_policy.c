#include "internal.h"
int vs_engine_event_policy_set(VsEngine *s,const VsEventPolicy *p) {
    if(!s||!ec_policy_valid(p)||s->generator.frame||s->event_runtime->frame||s->event_runtime->started||s->event_control.count||
       s->event_control.initialized||s->event_control.manual_sequence)return 0;
    s->event_control.policy=*p;return 1;
}
int vs_engine_event_policy_get(const VsEngine *s,VsEventPolicy *p) {
    if(!s||!p)return 0;*p=s->event_control.policy;return 1;
}
int vs_engine_event_policy_stats(const VsEngine *s,VsEventPolicyStats *p) {
    if(!s||!p)return 0;*p=s->event_control.policy_stats;return 1;
}
