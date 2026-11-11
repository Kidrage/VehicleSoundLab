#ifndef VSL_REFERENCE_OSC_MODEL_H
#define VSL_REFERENCE_OSC_MODEL_H
#include <stddef.h>
#include <stdint.h>
#define RO_MAX_ROWS 256
#define RO_MAX_SEGMENTS 12000
typedef struct { double amplitude0,amplitude1,phase0,omega0,c2,c3; } RoChannel;
typedef struct { unsigned group;RoChannel channel[2]; } RoPartial;
typedef struct { uint64_t start;unsigned frames,count;RoPartial *partials; } RoSegment;
typedef struct { unsigned rate,count;uint64_t frames;RoSegment *segments; } RoModel;
/* File/allocation work happens before render. The model stores OSC parameters,
   never PCM samples. It describes a fitted excerpt, not a learned RPM model. */
int ro_model_load(const char *path,RoModel *model);
void ro_model_free(RoModel *model);
#endif
