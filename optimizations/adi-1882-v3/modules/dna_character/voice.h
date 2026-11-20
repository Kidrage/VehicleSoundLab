#ifndef VSL_DNA_CHARACTER_VOICE_H
#define VSL_DNA_CHARACTER_VOICE_H
#include <stdint.h>
#include "control.h"
#include "fine_idle_layer/profile.h"
typedef struct DchVoice DchVoice;
typedef struct {unsigned state;float rpm,idle_rpm,envelope;} DchContext;
typedef struct {float line[2],air[2],idle_weight,air_weight;} DchFrame;
/* Non-RT creation/prewarm; optional fingerprint is borrowed immutable.
   Existing atlas line/detail supplied per sample; no second vehicle clock. */
DchVoice *dch_create(const FiProfile *fingerprint,uint64_t seed,const DchControl *control);
void dch_destroy(DchVoice *voice);
void dch_mechanical_amount(DchVoice *voice,float amount);
void dch_character_amounts(const DchVoice *voice,float *line,float *air);
int dch_set(DchVoice *voice,const DchControl *control);
/* RT: no allocation/IO/room. Advances innovations even at zero gain. */
int dch_tick(DchVoice *voice,const DchContext *context,const float line[2],
             const float air[2],DchFrame *output);
int dch_tick_split(DchVoice *voice,const DchContext *context,const float line[2],
             const float air[2],float air_envelope,DchFrame *output);
#endif
