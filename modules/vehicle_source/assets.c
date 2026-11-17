#include "internal.h"
#include <stdlib.h>
VsAssets *vs_assets_from_atlas(const AdConfig *config) {
    VsAssets *a;AdConfig c;
    if(!config)return NULL;
    c=*config;c.channels=2;c.scene_mode=AD_SCENE_STEREO_BED;
    a=calloc(1,sizeof *a);
    if(a&&!at_assets_copy(&a->owned,&c)){free(a);return NULL;}
    return a;
}
void vs_assets_destroy(VsAssets *assets){if(assets){free(assets->states);free(assets);}}
