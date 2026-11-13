#ifndef VSL_ATLAS_DRIVE_SOURCE_H
#define VSL_ATLAS_DRIVE_SOURCE_H
#include "drive/types.h"
#include <stdint.h>

enum { AD_SOURCE_DNA, AD_SOURCE_BODY, AD_SOURCE_RESIDUAL,
       AD_SOURCE_RESONANT, AD_SOURCE_COHERENT_LOW, AD_SOURCE_ADDED,
       AD_SOURCE_LAYERS };
typedef struct { double stereo[AD_SOURCE_LAYERS][2]; } AdSourceFrame;
typedef struct {
    const VslDrive *drive; /* Read-only existing controller; never step it here. */
    double envelope,body_envelope;
    uint64_t frame;
} AdSourceContext;
typedef struct {
    void *state; /* Exclusive caller-owned state, initialized outside render. */
    int (*tick)(void *state,const AdSourceContext *context,AdSourceFrame *frame);
} AdSourceProcessor;

int ad_source_valid(const AdSourceProcessor *processor);
/* RT, pre-spatial source stage. Processor may alter recording-source stems;
   events/startup/catch/auxiliary remain separate. Finite outputs required.
   Callback state has no generic serializer: schema8 takes reject this option. */
int ad_source_apply(const AdSourceProcessor *processor,const AdSourceContext *context,AdSourceFrame *frame);
#endif
