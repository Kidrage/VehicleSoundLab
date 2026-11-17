#ifndef VSL_DNA_CHARACTER_VOICE_H
#define VSL_DNA_CHARACTER_VOICE_H
#include <stdint.h>
#include "control.h"
#include "fine_idle_layer/profile.h"
typedef struct DchVoice DchVoice;
typedef struct {unsigned state;double rpm,idle_rpm,envelope;} DchContext;
typedef struct {double line[2],air[2],idle_weight,air_weight;} DchFrame;
/* Non-RT creation/prewarm; optional fingerprint is borrowed immutable.
   Existing atlas line/detail supplied per sample; no second vehicle clock. */
DchVoice *dch_create(const FiProfile *fingerprint,uint64_t seed,const DchControl *control);
void dch_destroy(DchVoice *voice);
int dch_set(DchVoice *voice,const DchControl *control);
/* RT: no allocation/IO/room. Advances innovations even at zero gain. */
int dch_tick(DchVoice *voice,const DchContext *context,const double line[2],
             const double air[2],DchFrame *output);
#endif
