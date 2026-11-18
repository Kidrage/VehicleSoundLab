#include "dna_character/dynamics.h"
#include "core/modules.h"
#include "../../presets/events/reference_afterfire_G_v2.h"
#include "../../presets/events/reference_afterfire_G_v3.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"dynamics check failed at %d\n",__LINE__);free(e);return 1;}}while(0)
int main(void) {
    VslEngine *e=calloc(1,sizeof *e);double line,air;CHECK(e);
    CHECK(es_profile_valid(&vsl_reference_afterfire_G_v2)&&ec_policy_valid(&vsl_reference_afterfire_G_policy));
    CHECK(vsl_reference_afterfire_G_v2.mode_count==3&&vsl_reference_afterfire_G_v2.band_count==2);
    CHECK(es_profile_valid(&vsl_reference_afterfire_G_v3));
    CHECK(vsl_reference_afterfire_G_v3.mode_count==3&&vsl_reference_afterfire_G_v3.band_count==2);
    e->drive.rpm=4000;e->drive.lifecycle=VSL_RUNNING;e->drive.combustion=1;e->drive.shift_gain=1;
    e->voice.dna_gain=.19;e->voice.state_mix[VSL_OVERRUN]=1;
    dch_dynamics_targets(e,&line,&air);CHECK(fabs(line-.50)<1e-14&&fabs(air-.64)<1e-14);
    e->drive.rpm=vsl_profile(e->target.profile)->idle_rpm;
    dch_dynamics_targets(e,&line,&air);CHECK(line==.19&&air==.19);
    e->drive.rpm=4000;e->drive.lifecycle=VSL_STOPPING;
    dch_dynamics_targets(e,&line,&air);CHECK(line==.19&&air==.19);
    e->drive.lifecycle=VSL_RUNNING;e->voice.state_mix[VSL_OVERRUN]=0;e->voice.state_mix[VSL_PULL]=1;
    e->drive.throttle=.9;e->drive.load=.9;e->voice.dna_gain=1.1;
    dch_dynamics_targets(e,&line,&air);CHECK(line==1.1&&air==1.1);
    e->drive.throttle=0;e->drive.load=-.1;e->drive.shift_gain=0;
    e->voice.dna_gain=.01;e->voice.state_mix[VSL_PULL]=0;e->voice.state_mix[VSL_SHIFT_CUT]=1;
    dch_dynamics_targets(e,&line,&air);CHECK(fabs(line-.20)<1e-14&&fabs(air-.48)<1e-14);
    free(e);puts("PASS: independent coasting line/air targets, preserved idle/start/power, partial shift retention");return 0;
}
