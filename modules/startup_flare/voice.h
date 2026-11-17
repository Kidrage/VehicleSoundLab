#ifndef VSL_STARTUP_FLARE_VOICE_H
#define VSL_STARTUP_FLARE_VOICE_H
#include <stdint.h>
typedef struct SflVoice SflVoice;
SflVoice *sfl_create(void);
void sfl_destroy(SflVoice *voice);
/* Single engine sample clock/lifecycle. Output is before master gain.
   Foreground replaces the engine, then hands back to its ongoing DNA.
   Duration comes from the same lifecycle profile; no private vehicle driver. */
int sfl_tick(SflVoice *voice,int lifecycle,uint64_t frame,double duration,
             double amount,double stereo[2],double *background);
#endif
