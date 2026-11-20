#include "fixed_assets.h"
#include "vehicle_source/internal.h"
#include <stddef.h>
#ifndef VSL_FIXED_V10
#error fixed_assets.c requires VSL_FIXED_V10
#endif
#include "fixed_assets.inc"
static unsigned char fixed_assets_used;
VsAssets *vsl_fixed_assets_acquire(void){
    if(fixed_assets_used)return NULL;
    fixed_assets_used=1;
    /* Legacy asset API uses a mutable handle; production never writes these
       parameters. This cast does not copy them into a second RAM allocation. */
    return (VsAssets *)(void *)&fixed_assets;
}
void vsl_fixed_assets_release(VsAssets *assets){
    if(assets==(const void *)&fixed_assets)fixed_assets_used=0;
}
AdControl vsl_fixed_initial(void){return fixed_initial;}
