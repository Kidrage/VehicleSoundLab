#include "audition.h"
#include "core/modules.h"
#include "spatial/propagation.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
static const struct { const char *name;unsigned mask; } groups[VSL_AUDITION_GROUPS]={
    {"exhaust",(1u<<VSL_EXHAUST_L)|(1u<<VSL_EXHAUST_R)},
    {"body",1u<<VSL_BODY},{"mechanical",1u<<VSL_MECHANICAL},{"intake",1u<<VSL_INTAKE},
    {"air",(1u<<VSL_AIR_L)|(1u<<VSL_AIR_R)},{"events",1u<<VSL_EVENT},
    {"road_wind",(1u<<VSL_ROAD)|(1u<<VSL_WIND)}
};
unsigned vsl_audition_group_mask(int group) { return group>=0&&group<VSL_AUDITION_GROUPS?groups[group].mask:0; }
const char *vsl_audition_group_name(int group) { return group>=0&&group<VSL_AUDITION_GROUPS?groups[group].name:"invalid"; }
int vsl_audition_mode_name(int mode,char *name,size_t capacity) {
    int n;
    if(mode<0||mode>=VSL_AUDITION_MODES||!name||!capacity)return 0;
    n=mode?snprintf(name,capacity,"%s_%s",mode%2?"solo":"without",groups[(mode-1)/2].name):snprintf(name,capacity,"full");
    return n>=0&&(size_t)n<capacity;
}
void vsl_audition_init(VslSourceAudition *state) {
    int g;memset(state,0,sizeof *state);
    for(g=0;g<VSL_AUDITION_GROUPS;++g)vsl_propagation_init(&state->group[g].propagation);
}
void vsl_audition_update(VslEngine *e,VslSourceAudition *state,int channels) {
    int g;for(g=0;g<VSL_AUDITION_GROUPS;++g)vsl_audition_scene_update(e,&state->group[g],channels);
}
static float monitored(VslSourceAudition *state,int mode,double x) {
    if(fabs(x)>.95||!isfinite(x))++state->clipped[mode];
    return (float)vsl_clamp(x,-.95,.95);
}
void vsl_audition_tick(VslEngine *e,VslSourceAudition *state,const VslObjectFrame *objects,
    const double *full,float *views,int channels) {
    int g,c;double solo[VSL_MAX_CHANNELS];
    for(c=0;c<channels;++c) {
        float x=monitored(state,0,full[c]*e->smooth.master);
        if(views)views[c]=x;
    }
    for(g=0;g<VSL_AUDITION_GROUPS;++g) {
        int only=1+2*g,without=only+1;
        vsl_audition_scene_tick(e,&state->group[g],objects,groups[g].mask,solo,channels);
        for(c=0;c<channels;++c) {
            float a=monitored(state,only,solo[c]*e->smooth.master);
            float b=monitored(state,without,(full[c]-solo[c])*e->smooth.master);
            if(views) { views[only*channels+c]=a;views[without*channels+c]=b; }
        }
    }
}
