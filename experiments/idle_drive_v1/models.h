#ifndef VSL_IDLE_DRIVE_MODELS_H
#define VSL_IDLE_DRIVE_MODELS_H
#include "../modal_idle_v1/models.h"
#include "modal_layer/profile.h"
typedef struct { MiModels source;MlProfile idle; } IdModels;
int id_models_load(IdModels *models);
int id_models_valid(const IdModels *models);
#endif
