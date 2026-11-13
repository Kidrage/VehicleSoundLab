#define _CRT_SECURE_NO_WARNINGS
#include "monitor.h"
#include "modal_source/io.h"
#include "modal_texture/io.h"
#include "spectral_texture/io.h"
#include <stdio.h>
#include <stdlib.h>
int fm_models_load(FmModels *out,const char *directory) {
    FmModels *p;char path[2048];int n,ok=0;
    if(!out||!directory)return 0;p=calloc(1,sizeof *p);if(!p)return 0;
#define LOAD(name,reader,field) do{n=snprintf(path,sizeof path,"%s/%s",directory,name);if(n<0||(size_t)n>=sizeof path||!reader(path,&p->field))goto done;}while(0)
    LOAD("experiments/modal_idle_v1/F2_fixed_idle.msource",ms_profile_load,core);
    LOAD("experiments/idle_microtexture_v1/F2_fast_detail.mtexture",mt_profile_load,motion);
    LOAD("experiments/spectral_texture_v1/F2_fine_static.sfir",sf_profile_load,fine);
#undef LOAD
    if(p->motion.count>p->fine.count)goto done;
    *out=*p;ok=1;
done:free(p);return ok;
}
