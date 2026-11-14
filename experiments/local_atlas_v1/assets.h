#ifndef VSL_LOCAL_ATLAS_ASSETS_H
#define VSL_LOCAL_ATLAS_ASSETS_H
#include "dna_atlas/voice.h"
typedef struct {
    SdProfile models[SA_MAX_ANCHORS];
    SaBank bank;
    unsigned align_orders;
    char paths[SA_MAX_ANCHORS][4096];
} LaAssets;
/* Non-RT, transactional UTF8 manifest load. Sorted profiles remain owned here;
   the bank borrows them. Storage must stay at this address during rendering. */
int la_assets_load(LaAssets *assets,const char *path);
#endif
