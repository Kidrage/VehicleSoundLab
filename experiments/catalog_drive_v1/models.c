#include "models.h"
#include "decel_models.h"
#include "core/engine.h"
#include "../atlas_monitor_v1/models.h"
#include "../full_recipe_drive_v1/models.h"
#include "../fine_idle_drive_v1/models.h"
#include "../stationary_bridge_v1/models.h"
#include <stdlib.h>
typedef struct {FrModels moving;FidModels idle;AmModels other;SaBank bank;StProfile startup;CbProfile catching;SdProfile synthetic;SbmModels stationary;CdmModels decel;} Inputs;
DcPreset *cd_models_load(int selection) {
    Inputs *m;DcPreset *p=NULL;AdConfig cfg={0};AdControl c={0};const DcInfo *info=dc_info(selection);
    if(!info)return NULL;m=calloc(1,sizeof *m);if(!m)return NULL;
    cfg.seed=48271;cfg.profile=info->profile;cfg.channels=2;cfg.root_per_rpm=1./120;cfg.scene_mode=AD_SCENE_STEREO_BED;
    c.drive.mode=VSL_BENCH;c.drive.gear=c.drive.automatic=c.drive.backfire=1;c.drive.rpm=1200;c.drive.load=.8;
    c.mix.gain=.25;c.mix.detail=1;c.mix.width=1;
    if(selection<=DC_MOVING) {
        if(!fr_models_load(&m->moving))goto done;
        cfg.bank=&m->moving.bank;cfg.resonant_bank=&m->moving.resonance;cfg.recipe_bank=&m->moving.recipe;
        c.mix.resonant_gain=c.mix.coherent_low_gain=1;c.drive.rpm=m->moving.dna.base_hz/cfg.root_per_rpm;
        if(selection==DC_FINE_IDLE) {
            if(!fid_models_load(&m->idle))goto done;cfg.fine_idle_profile=&m->idle.idle;
            c.drive.rpm=850;c.drive.load=0;c.mix.idle_mix=c.mix.idle_detail=1;c.mix.idle_motion=.5;
        }
    }else if(selection<=DC_SETTLE) {
        int variant=selection-DC_EXTERIOR;
        if(!am_models_load_variant(&m->other,variant,variant==2)||!am_models_bank(&m->other,&m->bank))goto done;
        cfg.bank=&m->bank;cfg.residual_bank=m->other.residual.count?&m->other.residual:NULL;
        if(selection==DC_CABIN)c.drive.rpm=6500;
        if(selection==DC_SETTLE) {
            if(!am_startup_load(&m->startup)||!am_catch_load(&m->catching))goto done;
            cfg.startup_profile=&m->startup;cfg.catch_profile=&m->catching;
            cfg.root_per_rpm=m->other.profile[0].base_hz/vsl_profile(VSL_V10)->idle_rpm;
            c.drive.rpm=vsl_profile(VSL_V10)->idle_rpm;c.drive.load=0;c.mix.startup_gain=c.mix.catch_gain=.5;
        }
    }else if(selection==DC_STATIONARY5) {
        if(!sbm_models_load(&m->stationary))goto done;
        cfg.bank=&m->stationary.bank;cfg.resonant_bank=&m->stationary.resonance;cfg.recipe_bank=&m->stationary.recipe;
        c.mix.resonant_gain=1;c.drive.rpm=m->stationary.dna[2].base_hz/cfg.root_per_rpm;
    }else if(selection==DC_DECEL) {
        if(!cdm_models_load(&m->decel))goto done;
        cfg.bank=&m->decel.bank;cfg.resonant_bank=&m->decel.resonance;cfg.recipe_bank=&m->decel.recipe;
        c.mix.resonant_gain=1;c.drive.rpm=m->decel.dna.base_hz/cfg.root_per_rpm;
    }else {
        const SdProfile *models[1]={&m->synthetic};
        if(!sd_profile_load(selection==DC_WARM?"voices/dna_bank_v1/Warm Additive.model":"voices/dna_bank_v1/Hollow Spectrum.model",&m->synthetic)||
           !sa_bank_init(&m->bank,models,1,0))goto done;
        cfg.bank=&m->bank;c.drive.rpm=4000;cfg.root_per_rpm=m->synthetic.base_hz/4000;
    }
    p=dc_preset_create(selection,&cfg,&c);
done:free(m);return p;
}
