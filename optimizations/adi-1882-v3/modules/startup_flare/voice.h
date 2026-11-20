#ifndef VSL_STARTUP_FLARE_VOICE_H
#define VSL_STARTUP_FLARE_VOICE_H
#include <stdint.h>
typedef struct SflVoice SflVoice;
SflVoice *sfl_create(void);
void sfl_destroy(SflVoice *voice);
void sfl_character(SflVoice *voice,float line,float air);
/* Single engine sample clock/lifecycle. Output is before master gain.
   Foreground replaces the engine, then hands back to its ongoing DNA.
   Duration comes from the same lifecycle profile; no private vehicle driver.
   Amount 0..2.6, with 0.5 equal to the V17 nominal foreground level. */
int sfl_tick(SflVoice *voice,int lifecycle,uint64_t frame,float duration,
             float amount,float stereo[2],float *background);
#endif
