#ifndef VSL_SOURCE_AUDITION_H
#define VSL_SOURCE_AUDITION_H
#include "core/engine.h"
#include "session/take.h"
#include <stddef.h>
#define VSL_AUDITION_GROUPS 7
#define VSL_AUDITION_MODES (1+2*VSL_AUDITION_GROUPS)
typedef struct {
    VslSpatial group[VSL_AUDITION_GROUPS];
    uint64_t clipped[VSL_AUDITION_MODES];
} VslSourceAudition;
void vsl_audition_init(VslSourceAudition *state);
unsigned vsl_audition_group_mask(int group);
const char *vsl_audition_group_name(int group);
int vsl_audition_mode_name(int mode,char *name,size_t capacity);
void vsl_audition_update(VslEngine *e,VslSourceAudition *state,int channels);
void vsl_audition_tick(VslEngine *e,VslSourceAudition *state,const VslObjectFrame *objects,
    const double *full,float *views,int channels);
void vsl_audition_scene_update(VslEngine *e,VslSpatial *state,int channels);
void vsl_audition_scene_tick(VslEngine *e,VslSpatial *state,const VslObjectFrame *objects,
    unsigned mask,double *output,int channels);
int vsl_audition_process_layout(VslEngine *e,VslSourceAudition *state,float *output,
    unsigned frames,int channels,float *stems,float *views);
unsigned vsl_audition_take_process(VslTakePlayer *player,VslEngine *e,VslSourceAudition *state,
    float *output,unsigned frames,int channels,float *stems,float *views);
#endif
