#ifndef VSL_SCENE_MONITOR_MODELS_H
#define VSL_SCENE_MONITOR_MODELS_H
#include "recipe.h"
#include <wchar.h>
typedef struct { SdProfile dna, low; int has_low; } SmoModels;
/* Non-realtime, transactional; never call while destination is being rendered. */
int smo_models_read(SmoModels *models, const wchar_t *dna_path, const wchar_t *low_path);
#endif
