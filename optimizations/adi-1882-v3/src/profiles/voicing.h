#ifndef VSL_VOICING_PROFILE_H
#define VSL_VOICING_PROFILE_H
#include "core/voice_types.h"
/* Engineering voicing controls, independent of cylinder/firing geometry.
   No number in this table is claimed as fitted Lamborghini telemetry. */
typedef struct {
    float level[VSL_LAYERS];
    float tilt_delta, cutoff_ratio;
} VslStateTone;
typedef struct {
    VslStateTone state[VSL_OPERATING_COUNT];
    float attack[VSL_LAYERS], release[VSL_LAYERS];
    float cut_depth[VSL_LAYERS], cut_seconds[VSL_LAYERS], recover_seconds[VSL_LAYERS];
    float catch_level[VSL_LAYERS];
    float rev_match_relief[VSL_LAYERS];
} VslVoicingProfile;
const VslVoicingProfile *vsl_voicing_profile(int profile);
const char *vsl_layer_name(int layer);
#endif
