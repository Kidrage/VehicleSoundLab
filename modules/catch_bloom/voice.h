#ifndef VSL_CATCH_BLOOM_VOICE_H
#define VSL_CATCH_BLOOM_VOICE_H
#include "profile.h"
#include "filter.h"
typedef struct {
    CbProfile profile;CbFilter filter[CB_MAX_MODES];
    double envelope,target,amount,amount_target,attack,release,follow;
    int initialized;
} CbVoice;
/* Owns copied profile; caller allocates. No PCM, RNG, controller or I/O. */
int cb_voice_init(CbVoice *voice,const CbProfile *profile,double amount);
/* Progress comes from the unique driver's CATCH lifecycle; no private clock. */
int cb_voice_set(CbVoice *voice,int gate,double progress,double amount);
/* Produces only additive coherent LF delta from the continuous DNA input.
   Input/delta are interleaved L/R, may alias. Filters advance even at zero. */
int cb_voice_process(CbVoice *voice,const double *input,double *delta,unsigned frames);
#endif
