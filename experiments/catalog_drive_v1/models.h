#ifndef VSL_CATALOG_DRIVE_MODELS_H
#define VSL_CATALOG_DRIVE_MODELS_H
#include "drive_catalog/catalog.h"
/* Non-RT adapter only. Existing file readers/recipe parameters, owned result.
   No live selection or callbacks are invoked here. */
DcPreset *cd_models_load(int selection);
#endif
