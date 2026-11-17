#ifndef VSL_STARTUP_SCENE_H
#define VSL_STARTUP_SCENE_H
#include "voice.h"
typedef struct {
    double level,core,texture;unsigned count;double knot[4],pitch[4];
} ScGesture;
typedef struct {
    double start,duration[3],handoff,reference_gain,rotation_scale;
    ScGesture gesture[3];
} ScTimeline;
/* Same frame clock as the host engine. Borrowed voices must be fresh at
   first_frame=0 and ticked continuously. Caller owns model/voice lifetime.
   parts optionally receives prelude/crank/catch/idle, interleaved8channels.
   There is no original audio, independent vehicle controller or room model. */
int sc_timeline_valid(const ScTimeline *timeline);
int sc_mix_scene(ScVoice *const voice[3],const ScTimeline *timeline,uint64_t first_frame,
                 const float *base,float *mix,float *parts,unsigned frames);
#endif
