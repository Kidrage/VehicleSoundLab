#ifndef VSL_STARTUP_CHARACTER_H
#define VSL_STARTUP_CHARACTER_H
#include "spectral_texture/voice.h"
#include "ridge.h"
#include "crank_rotation/voice.h"
#define SC_STAGES 3
#define SC_POINTS 9
typedef struct ScVoice ScVoice;
/* Source spectra are stochastic excitation filters, not room IRs or audio.
   Non-RT creation owns compiled kernels; tick allocates nothing. */
ScVoice *sc_create(const SfProfile *profiles[SC_STAGES],const float envelope[SC_POINTS],
                   float variation,uint64_t seed);
void sc_destroy(ScVoice *voice);
/* RT-safe finite-gesture rearm; keeps spectral/RNG state, clears onset gate. */
void sc_rearm(ScVoice *voice);
int sc_set_rotation(ScVoice *voice,const CkProfile *profile,uint64_t seed);
/* Optional sparse moving OSC core, configured before processing. */
int sc_set_ridges(ScVoice *voice,const ScRidge *ridges,unsigned count,unsigned reference_frames,float variation,float pitch,uint64_t seed);
/* Normalized crank progress is independent of sample rate/pitch. The sole
   vehicle lifecycle supplies progress/gate; this module integrates no RPM. */
int sc_tick(ScVoice *voice,float progress,int gate,float strength,float stereo[2]);
/* Expressive event controls, opt-in. Pure OSC pitch moves independently of
   residual spectral colour; source mixture gains are not physical separation. */
int sc_tick_expression(ScVoice *voice,float progress,int gate,float strength,
                       float pitch,float core_gain,float texture_gain,float stereo[2]);
#endif
