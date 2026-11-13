#include "models.h"
#include "../idle_state_v1/study.h"
#include <string.h>
int id_models_valid(const IdModels *m) {
    return m&&m->idle.modal==&m->source.modal&&m->idle.detail==&m->source.detail&&ml_profile_valid(&m->idle);
}
int id_models_load(IdModels *m) {
    if(!m)return 0;
    memset(m,0,sizeof *m);
    if(!mi_models_load(&m->source,"experiments/modal_idle_v1/F2_fixed_idle.msource",
                      "experiments/modal_idle_v1/F2_fixed_idle.rdetail"))return 0;
    m->idle.modal=&m->source.modal;m->idle.detail=&m->source.detail;
    m->idle.modal_ratio=m->idle.modal_gain=m->idle.detail_gain=1;
    m->idle.level_gain=IS_IDLE_LEVEL_GAIN;
    m->idle.attack_frames=m->idle.release_frames=IS_IDLE_FADE_FRAMES;
    return id_models_valid(m);
}
