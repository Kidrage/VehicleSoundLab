#ifndef VSL_EVENT_SYNTH_INTERNAL_H
#define VSL_EVENT_SYNTH_INTERNAL_H
#include "api.h"
#define ES_PI 3.14159265358979323846f
float es_random(uint32_t *state);
float es_attack(uint64_t age,float seconds);
unsigned es_contour_index(const EsProfile *profile,float hz);
float es_contour_gain(const EsContour *contour,float seconds);
void es_oscillator_init(EsOscillator *osc,const EsMode *mode,const EsRequest *request,float variation);
float es_oscillator_tick(EsOscillator *osc);
void es_noise_init(EsNoiseBand *band,const EsBand *profile,const EsRequest *request);
float es_noise_tick(EsNoiseBand *band,float noise,uint64_t age,int gated);
void es_color_init(EsColorSection sections[2],float hz);
float es_color_tick(EsColorSection sections[2],float input);
void es_voice_begin(EsVoice *voice,const EsProfile *profile,const EsRequest *request);
float es_voice_tick(EsVoice *voice);
int es_voice_finished(const EsVoice *voice);
void es_notice(EsPool *pool,const EsRequest *request,unsigned slot,unsigned action,unsigned reason);
#endif
