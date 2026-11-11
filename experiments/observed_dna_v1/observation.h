#ifndef VSL_OBSERVATION_H
#define VSL_OBSERVATION_H
#include "core/engine.h"
/* One native custom-DNA engine for each microphone observation. Not banks. */
typedef struct { VslEngine channel[2]; } VslObservedDna;
int vsl_observed_init(VslObservedDna *state,const char *left,const char *right);
void vsl_observed_process(VslObservedDna *state,float *stereo,unsigned frames);
#endif
