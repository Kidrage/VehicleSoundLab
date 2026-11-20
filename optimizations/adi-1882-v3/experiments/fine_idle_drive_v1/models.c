#include "models.h"
#include "modal_source/io.h"
#include "modal_texture/io.h"
#include "spectral_texture/io.h"
#include "../idle_state_v1/study.h"
#include <string.h>
int fid_models_valid(const FidModels *m) {
    return m&&m->idle.modal==&m->modal&&m->idle.motion==&m->motion&&
        m->idle.detail==&m->detail&&fi_profile_valid(&m->idle);
}
int fid_models_load(FidModels *m) {
    if(!m)return 0;memset(m,0,sizeof *m);
    if(!ms_profile_load("experiments/modal_idle_v1/F2_fixed_idle.msource",&m->modal)||
       !mt_profile_load("experiments/modal_texture_v1/F2_amplitude.mtexture",&m->motion)||
       !sf_profile_load("experiments/spectral_texture_v1/F2_fine_static.sfir",&m->detail))return 0;
    m->idle=(FiProfile){&m->modal,&m->motion,&m->detail,1,1,1,IS_IDLE_LEVEL_GAIN,IS_IDLE_FADE_FRAMES,IS_IDLE_FADE_FRAMES};
    return fid_models_valid(m);
}
