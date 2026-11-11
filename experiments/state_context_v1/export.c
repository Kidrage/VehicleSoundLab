/* Read-only export of the linked frozen runtime's actual profile tables. */
#include "core/engine.h"
#include "drive/drive.h"
#include "drive/shift.h"
#include "drive/fueling.h"
#include "profiles/voicing.h"
#include "profiles/lifecycle.h"
#include "profiles/transmission.h"
#include "profiles/fueling.h"
#include <stdio.h>

static void array(const double *value,int count) {
    int i;putchar('[');
    for(i=0;i<count;++i)printf("%s%.17g",i?",":"",value[i]);
    putchar(']');
}

int main(void) {
    const VslVoicingProfile *voice=vsl_voicing_profile(VSL_V10);
    const VslLifecycleProfile *life=vsl_lifecycle_profile(VSL_V10);
    const VslTransmissionProfile *shift=vsl_transmission_profile(VSL_V10);
    const VslFuelingProfile *fuel=vsl_fueling_profile(VSL_V10);
    int i,shared=1;
    for(i=0;i<VSL_PROFILE_COUNT;++i)shared=shared&&voice==vsl_voicing_profile(i)&&
        life==vsl_lifecycle_profile(i)&&shift==vsl_transmission_profile(i)&&fuel==vsl_fueling_profile(i);
    printf("{\"schema\":\"vsl.runtime-state-tables/1\",\"runtime\":\"%s\",\"shared_five_templates\":%s,",VSL_VERSION,shared?"true":"false");
    printf("\"layers\":[");
    for(i=0;i<VSL_LAYERS;++i)printf("%s\"%s\"",i?",":"",vsl_layer_name(i));
    printf("],\"operating\":[");
    for(i=0;i<VSL_OPERATING_COUNT;++i) {
        printf("%s{\"name\":\"%s\",\"level\":",i?",":"",vsl_operating_name((VslOperating)i));
        array(voice->state[i].level,VSL_LAYERS);
        printf(",\"tilt_delta\":%.17g,\"cutoff_ratio\":%.17g}",voice->state[i].tilt_delta,voice->state[i].cutoff_ratio);
    }
    printf("],\"layer_envelopes_seconds\":{\"attack\":");array(voice->attack,VSL_LAYERS);
    printf(",\"release\":");array(voice->release,VSL_LAYERS);
    printf(",\"cut\":");array(voice->cut_seconds,VSL_LAYERS);
    printf(",\"recover\":");array(voice->recover_seconds,VSL_LAYERS);
    printf("},\"cut_depth\":");array(voice->cut_depth,VSL_LAYERS);
    printf(",\"lifecycle\":[");
    for(i=VSL_OFF;i<=VSL_STOPPING;++i)printf("%s\"%s\"",i?",":"",vsl_lifecycle_name((VslLifecycle)i));
    printf("],\"shift_stages\":[");
    for(i=VSL_SHIFT_NONE;i<=VSL_SHIFT_ENGAGE;++i)printf("%s\"%s\"",i?",":"",vsl_shift_stage_name((VslShiftStage)i));
    printf("],\"fuel_states\":[");
    for(i=VSL_FUEL_OFF;i<=VSL_FUEL_RESUME;++i)printf("%s\"%s\"",i?",":"",vsl_fuel_mode_name((VslFuelMode)i));
    printf("],\"engineering_seconds\":{\"crank\":%.17g,\"catch_rise\":%.17g,\"catch_settle\":%.17g,\"stop\":%.17g,\"shift_disconnect\":%.17g,\"up_match_min\":%.17g,\"down_match_min\":%.17g,\"shift_engage\":%.17g,\"coupled_fuel_delay\":%.17g,\"neutral_fuel_delay\":%.17g},",life->crank_seconds,life->catch_rise_seconds,life->catch_settle_seconds,life->stopping_seconds,shift->disconnect,shift->up_match_min,shift->down_match_min,shift->engage,fuel->coupled_delay,fuel->neutral_delay);
    printf("\"scope\":\"Actual linked C profile tables, not measured vehicle data or final source gains.\"}\n");
    return shared?0:1;
}
