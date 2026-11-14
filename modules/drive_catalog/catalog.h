#ifndef VSL_DRIVE_CATALOG_H
#define VSL_DRIVE_CATALOG_H
#include "atlas_take/assets.h"
enum { DC_FINE_IDLE,DC_MOVING,DC_EXTERIOR,DC_CABIN,DC_SETTLE,DC_WARM,DC_HOLLOW,DC_COUNT };
enum { DC_INTAKE,DC_MECHANICAL,DC_AIR,DC_ROAD,DC_WIND,DC_STARTUP,DC_CATCH,DC_IDLE,DC_MOTION,DC_FINE,DC_AUX_COUNT };
typedef struct {const char *key,*title,*scope;int profile;} DcInfo;
typedef struct DcPreset DcPreset;
const DcInfo *dc_info(int selection);
/* Non-RT: copies all parameters, validates config/control; no borrowed model
   pointers survive. Failure returns NULL. Destroy only after audio stops. */
DcPreset *dc_preset_create(int selection,const AdConfig *config,const AdControl *initial);
void dc_preset_destroy(DcPreset *preset);
const AdConfig *dc_preset_config(const DcPreset *preset);
AdControl dc_preset_initial(const DcPreset *preset);
int dc_preset_selection(const DcPreset *preset);
/* Capability comes from actual live/embedded configuration, not launch flags. */
int dc_aux_enabled(const AdConfig *config,int layer);
const char *dc_aux_name(int layer);
double *dc_aux_amount(AdControl *control,int layer);
#endif
