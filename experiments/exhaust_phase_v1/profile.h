#ifndef VSL_EXPERIMENT_PHASE_PROFILE_H
#define VSL_EXPERIMENT_PHASE_PROFILE_H
typedef struct { const char *name;double hz[3],q,delay_seconds; } VslPhaseProfile;
const VslPhaseProfile *vsl_phase_profile(int mode);
#endif
