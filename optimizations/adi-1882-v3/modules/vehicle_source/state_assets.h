#ifndef VSL_VEHICLE_STATE_ASSETS_H
#define VSL_VEHICLE_STATE_ASSETS_H
#include "dna_assets.h"
#include "state_dna/api.h"
typedef struct {
    const SdProfile *const *anchors[SX_STATES];
    unsigned count[SX_STATES],align_orders;
    uint64_t seed;
    int vehicle_profile;
    float root_per_rpm,transition_seconds;
} VsStateDnaConfig;
/* Owned authored states only; no catalog sound layers are inherited. */
VsAssets *vs_assets_from_state_dna(const VsStateDnaConfig *config);
int vs_engine_state_dna(const VsEngine *engine,SxTelemetry *telemetry);
#endif
