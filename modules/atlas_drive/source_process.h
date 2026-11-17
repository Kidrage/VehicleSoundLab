#ifndef VSL_ATLAS_SOURCE_PROCESS_H
#define VSL_ATLAS_SOURCE_PROCESS_H
#include "render.h"
/* Same source clock/math/captures as the historical adapter, but no scene
   update/tick, speaker routing, propagation or room state is advanced.
   Configuration must use two channels. Spatial capture fields are rejected;
   native source captures and auxiliary raw/mixed identities remain available.
   This low-level adapter still borrows historical storage. New consumers use
   vehicle_source/api.h, which hides it and exposes no spatial controls. */
int ad_source_process(AdRender *source,float *monitor,unsigned frames,const AdCapture *capture);
typedef struct {
    void *state;
    void (*step)(void *state,VslDrive *driver,const VslParams *params,uint64_t frame);
    /* Optional sample hook on the SAME clock, after continuous synthesis. */
    int (*sample)(void *state,uint64_t frame);
    /* Optional authored state-DNA generator; must advance the main clock once.
       Raw/full and complementary body use the same harmonic contributions. */
    int (*dna)(void *state,SaVoice *main,const HbBand *band,double stereo[2],double body[2]);
    /* Optional dry-source voicing after all continuous generators, before
       master gain. Startup/events/auxiliary are deliberately outside it. */
    int (*character)(void *state,const AdSourceContext *context,AdSourceFrame *frame);
    /* Optional production mechanical feature in place of historical templates. */
    void (*auxiliary)(void *state,VslEngine *owner,DaVoice *voice,VslObjectFrame *raw,VslObjectFrame *mixed);
} AdSourceDriver;
/* Optional replacement of the single 200Hz driver step, not a second driver. */
int ad_source_process_controlled(AdRender *source,float *monitor,unsigned frames,
    const AdCapture *capture,const AdSourceDriver *driver);
#endif
