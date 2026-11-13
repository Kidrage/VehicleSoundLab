#ifndef VSL_MODAL_SOURCE_VOICE_H
#define VSL_MODAL_SOURCE_VOICE_H
#include "profile.h"
#include <stdint.h>
#define MS_RAMP_FRAMES 864
typedef struct { double value,target,step;unsigned left; } MsRamp;
typedef struct {
    const MsProfile *profile;
    MsRamp ratio,gain;
    double rotation_ratio;
    double re[MS_MAX_MODES][2],im[MS_MAX_MODES][2];
    double cosine[MS_MAX_MODES],sine[MS_MAX_MODES];
    double dc[MS_MAX_MODES],ds[MS_MAX_MODES],weight[MS_MAX_MODES];
    uint64_t frame;
} MsVoice;
/* Non-RT validation before mutation. Ratio controls independent modal
   frequencies only; it is not an RPM or a full source/filter pitch control. */
int ms_voice_init(MsVoice *voice,const MsProfile *profile,double ratio,double gain);
/* RT: finite18ms monotonic ramps. Re-adopting the same target does not restart
   a ramp. Ratio0.25..4 and gain0..1; source validity may be much narrower. */
int ms_voice_set(MsVoice *voice,double ratio,double gain);
/* RT, preallocated outputs, no I/O or allocation. All modes advance at zero
   gain and while their anti-alias weights are zero. Invalid calls do not mutate. */
int ms_voice_tick(MsVoice *voice,double stereo[2]);
int ms_voice_process(MsVoice *voice,double *interleaved,unsigned frames);
#endif
