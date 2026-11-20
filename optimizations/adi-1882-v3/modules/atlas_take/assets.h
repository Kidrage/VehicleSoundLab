#ifndef VSL_ATLAS_TAKE_ASSETS_H
#define VSL_ATLAS_TAKE_ASSETS_H
#include "atlas_drive/render.h"
typedef struct {
    SdProfile profile[SA_MAX_ANCHORS];
    SaBank bank;
    RaBank residual;
    AdConfig config;
    StProfile startup;
    CbProfile catch_bloom;
    DrsBank resonant;
    DrcBank recipe;
    MsProfile idle_modal;
    RdtProfile idle_detail;
    MlProfile idle;
    MsProfile fine_modal;
    MtProfile fine_motion;
    SfProfile fine_detail;
    FiProfile fine_idle;
} AtAssets;
/* Owned, immutable render assets. Pointers stay inside this heap object. */
int at_assets_copy(AtAssets *destination,const AdConfig *source);
int at_assets_valid(const AtAssets *assets);
void at_assets_bind(AtAssets *assets,int has_residual);
#endif
