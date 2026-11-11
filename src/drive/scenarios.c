#include "scenarios.h"
#include "core/engine.h"
#include "core/modules.h"
#include <string.h>
int vsl_scenario_id(const char *name) {
    static const char *names[]={"fixed","auto","lift","shifts","neutral","downshift"};int i;
    for(i=0;i<VSL_SCENARIO_COUNT;++i)if(!strcmp(name,names[i]))return i;
    return -1;
}
static double ease(double value) { double x=vsl_clamp(value,0,1);return x*x*(3-2*x); }
/* Repeatable HOST INPUTS for audition. No simulated vehicle state is edited. */
void vsl_scenario_apply(int scenario,double t,VslParams *p) {
    if(scenario==VSL_SCENARIO_FIXED)return;
    if(scenario==VSL_SCENARIO_AUTO) { vsl_drive(t,p);return; }
    p->ignition=1;if(!p->start_id)p->start_id=1;
    p->auto_gear=0;p->brake=0;
    if(scenario==VSL_SCENARIO_LIFT) {
        p->drive_mode=VSL_BENCH;p->rpm=5000;p->gear=1;
        p->load=t<3?.85:(t<4.8?-.4:.85);
    } else if(scenario==VSL_SCENARIO_SHIFTS) {
        p->drive_mode=VSL_PEDALS;p->gear=t<4?1:(t<6?2:(t<10?3:2));
        p->throttle=t<1.6?0:(t<7?.85:(t<10?0:.30));
        p->brake=t>=8&&t<10?.60:0;
        if(t>=11.5)p->ignition=0;
    } else if(scenario==VSL_SCENARIO_DOWNSHIFT) {
        p->drive_mode=VSL_PEDALS;
        p->gear=t<4?1:(t<6?2:(t<8?3:(t<11.5?4:(t<13?3:(t<15?2:1)))));
        p->throttle=t<1.5?0:(t<9.5?.85:0);
        p->brake=t>=10.5?.45:0;
    } else if(scenario==VSL_SCENARIO_NEUTRAL) {
        p->drive_mode=VSL_PEDALS;p->gear=0;
        if(t<2)p->throttle=0;
        else if(t<3.5)p->throttle=.80*ease((t-2)/1.5);
        else if(t<4.7)p->throttle=.80*(1-ease((t-3.5)/1.2));
        else if(t<5.8)p->throttle=.90*ease((t-4.7)/1.1);
        else p->throttle=0;
    }
}
