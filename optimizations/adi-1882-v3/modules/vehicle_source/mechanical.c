#include "dsp/perf.h"
#include "internal.h"
#include "dna_character/mechanical.h"
#include <string.h>
#include <math.h>
void vs_mechanical_sample(void *state,VslEngine *engine,DaVoice *voice,VslObjectFrame *raw,VslObjectFrame *mixed);
void vs_mechanical_sample_impl(void *state,VslEngine *engine,DaVoice *voice,VslObjectFrame *raw,VslObjectFrame *mixed){
    float mono[1],*amount=voice->amount+DA_MECHANICAL;
    (void)state;
    #ifdef VSL_LEGACY_MECHANICAL
    dch_mechanical_tick(engine,voice->follow,mono);
#else
    (void)engine;mono[0]=0;
#endif
    *amount+=voice->follow*(voice->target[DA_MECHANICAL]-*amount);
    if(fabsf(*amount-voice->target[DA_MECHANICAL])<1e-12f)*amount=voice->target[DA_MECHANICAL];
    memset(raw,0,sizeof *raw);memset(mixed,0,sizeof *mixed);
    raw->sample[VSL_MECHANICAL]=mono[0];mixed->sample[VSL_MECHANICAL]=mono[0]* *amount;
}
void vs_mechanical_sample(void *state,VslEngine *engine,DaVoice *voice,VslObjectFrame *raw,VslObjectFrame *mixed){vsl_perf_enter(6);vs_mechanical_sample_impl(state,engine,voice,raw,mixed);vsl_perf_leave();}

