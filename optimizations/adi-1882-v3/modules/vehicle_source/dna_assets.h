#ifndef VSL_VEHICLE_SOURCE_DNA_ASSETS_H
#define VSL_VEHICLE_SOURCE_DNA_ASSETS_H
#include "api.h"
#include "sound_dna/profile.h"
typedef struct {
    const SdProfile *const *anchors;
    unsigned count,align_orders;
    uint64_t seed;
    int vehicle_profile;
    float root_per_rpm;
} VsDnaConfig;
/* Non-RT. Validates and copies every anchor; no source file dependency remains.
   This builds DNA assets only, without catalog LF/detail/idle/start textures.
   root_per_rpm is an explicit engineering mapping, not inferred ECU telemetry. */
VsAssets *vs_assets_from_dna(const VsDnaConfig *config);
#endif
