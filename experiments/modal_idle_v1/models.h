#ifndef VSL_MODAL_IDLE_MODELS_H
#define VSL_MODAL_IDLE_MODELS_H
#include "modal_source/profile.h"
#include "resonant_detail/profile.h"
typedef struct {MsProfile modal;RdtProfile detail;} MiModels;
/* Non-RT, fixed-idle study only; periodic detail is deliberately unsupported. */
int mi_models_valid(const MiModels *models);
int mi_models_load(MiModels *models,const char *modal_path,const char *detail_path);
#endif
