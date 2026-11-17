#include "internal.h"
#include "dna_character/mechanical.h"
#include <string.h>
#include <math.h>
void vs_mechanical_sample(void *state,VslEngine *engine,DaVoice *voice,VslObjectFrame *raw,VslObjectFrame *mixed){
    double mono[1],*amount=voice->amount+DA_MECHANICAL;
    (void)state;
    dch_mechanical_tick(engine,voice->follow,mono);
    *amount+=voice->follow*(voice->target[DA_MECHANICAL]-*amount);
    if(fabs(*amount-voice->target[DA_MECHANICAL])<1e-12)*amount=voice->target[DA_MECHANICAL];
    memset(raw,0,sizeof *raw);memset(mixed,0,sizeof *mixed);
    raw->sample[VSL_MECHANICAL]=mono[0];mixed->sample[VSL_MECHANICAL]=mono[0]* *amount;
}
