#include "internal.h"
#include <stdlib.h>
#include "dsp_support/storage.h"
VSL_STORAGE(vs_asset_storage,VsAssets,1,VSL_DDR)
VsAssets *vs_assets_acquire(void){return vs_asset_storage_acquire();}
void vs_assets_release(VsAssets *a){vs_asset_storage_release(a);}
VsAssets *vs_assets_from_atlas(const AdConfig *config) {
    VsAssets *a;AdConfig c;
    if(!config)return NULL;
    c=*config;c.channels=2;c.scene_mode=AD_SCENE_STEREO_BED;
    a=vs_assets_acquire();
    if(a&&!at_assets_copy(&a->owned,&c)){vs_assets_release(a);return NULL;}
    return a;
}
void vs_assets_destroy(VsAssets *assets){if(assets){vs_state_assets_release(assets);vs_assets_release(assets);}}
