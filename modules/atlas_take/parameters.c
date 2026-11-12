#include "parameters.h"
#define INPUT(name,kind) {#name,offsetof(AdControl,drive)+offsetof(AdInput,name),kind}
#define MIX(name,kind) {#name,offsetof(AdControl,mix)+offsetof(AdMix,name),kind}
static const AtField fields[]={
    INPUT(mode,1),INPUT(ignition,1),INPUT(start_id,1),INPUT(gear,1),INPUT(automatic,1),INPUT(backfire,1),
    INPUT(rpm,0),INPUT(load,0),INPUT(throttle,0),INPUT(brake,0),
    MIX(gain,0),MIX(detail,0),MIX(event_gain,0),MIX(width,0),MIX(room,0),MIX(perspective,0),
    MIX(spatial,1),MIX(propagation,1),MIX(residual_gain,0),MIX(body_mix,0),
    MIX(intake_gain,0),MIX(mechanical_gain,0),MIX(air_gain,0),MIX(road_gain,0),MIX(wind_gain,0),MIX(startup_gain,0),MIX(catch_gain,0),MIX(resonant_gain,0),MIX(coherent_low_gain,0)
};
const AtField *at_fields(unsigned *count) { *count=sizeof fields/sizeof fields[0];return fields; }
int at_control_same(const AdControl *a,const AdControl *b) {
    unsigned i,count;const AtField *f=at_fields(&count);
    if(!a||!b)return 0;
    for(i=0;i<count;++i) {
        const char *x=(const char*)a+f[i].offset,*y=(const char*)b+f[i].offset;
        if(f[i].integer?*(const int*)x!=*(const int*)y:*(const double*)x!=*(const double*)y)return 0;
    }
    return 1;
}
