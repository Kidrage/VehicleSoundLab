#ifndef VSL_VOICING_PROFILE_H
#define VSL_VOICING_PROFILE_H
#include "core/voice_types.h"
/* Engineering voicing controls, independent of cylinder/firing geometry.
   No number in this table is claimed as fitted Lamborghini telemetry. */
typedef struct {
    double level[VSL_LAYERS];
    double tilt_delta, cutoff_ratio;
} VslStateTone;
typedef struct {
    VslStateTone state[VSL_OPERATING_COUNT];
    double attack[VSL_LAYERS], release[VSL_LAYERS];
    double cut_depth[VSL_LAYERS], cut_seconds[VSL_LAYERS], recover_seconds[VSL_LAYERS];
    double catch_level[VSL_LAYERS];
    double rev_match_relief[VSL_LAYERS];
} VslVoicingProfile;
const VslVoicingProfile *vsl_voicing_profile(int profile);
const char *vsl_layer_name(int layer);
#endif
