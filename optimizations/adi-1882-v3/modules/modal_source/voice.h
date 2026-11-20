#ifndef VSL_MODAL_SOURCE_VOICE_H
#define VSL_MODAL_SOURCE_VOICE_H
#include "profile.h"
#include <stdint.h>
#define MS_RAMP_FRAMES 864
typedef struct { float value,target,step;unsigned left; } MsRamp;
typedef struct {
    const MsProfile *profile;
    MsRamp ratio,gain;
    float rotation_ratio;
    float re[MS_MAX_MODES][2],im[MS_MAX_MODES][2];
    float cosine[MS_MAX_MODES],sine[MS_MAX_MODES];
    float dc[MS_MAX_MODES],ds[MS_MAX_MODES],weight[MS_MAX_MODES];
    /* Rotation step is constant within each linear ratio ramp. Re-anchor to
       the exact ratio at least every64 samples and at every slope boundary. */
    float rotation_step,step_dc[MS_MAX_MODES],step_ds[MS_MAX_MODES];
    uint64_t frame;
} MsVoice;
/* Non-RT validation before mutation. Ratio controls independent modal
   frequencies only; it is not an RPM or a full source/filter pitch control. */
int ms_voice_init(MsVoice *voice,const MsProfile *profile,float ratio,float gain);
/* RT: finite18ms monotonic ramps. Re-adopting the same target does not restart
   a ramp. Ratio0.25..4 and gain0..1; source validity may be much narrower. */
int ms_voice_set(MsVoice *voice,float ratio,float gain);
/* RT, preallocated outputs, no I/O or allocation. All modes advance at zero
   gain and while their anti-alias weights are zero. Invalid calls do not mutate. */
int ms_voice_tick(MsVoice *voice,float stereo[2]);
/* Optional common-L/R amplitude per mode, in profile order. NULL preserves
   the original arithmetic. Finite nonnegative gains are checked before any
   state change; the caller supplies profile->count values. No phase change. */
int ms_voice_tick_gains(MsVoice *voice,const float *mode_gain,float stereo[2]);
int ms_voice_process(MsVoice *voice,float *interleaved,unsigned frames);
#endif
