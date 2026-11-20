#ifndef VSL_FINE_IDLE_DRIVE_MODELS_H
#define VSL_FINE_IDLE_DRIVE_MODELS_H
#include "fine_idle_layer/profile.h"
typedef struct {MsProfile modal;MtProfile motion;SfProfile detail;FiProfile idle;} FidModels;
int fid_models_load(FidModels *models);
int fid_models_valid(const FidModels *models);
#endif
