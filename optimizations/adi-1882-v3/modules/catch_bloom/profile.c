#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include <math.h>
#include <string.h>
int cb_profile_valid(const CbProfile *p) {
    unsigned i;
    if(!p||p->modes<1||p->modes>CB_MAX_MODES||!isfinite(p->rise_shape)||!isfinite(p->fall_shape)||
       p->rise_shape<.25f||p->rise_shape>8||p->fall_shape<.25f||p->fall_shape>8||
       !isfinite(p->attack_seconds)||p->attack_seconds<1.f/48000||p->attack_seconds>.1f||
       !isfinite(p->release_seconds)||p->release_seconds<1.f/48000||p->release_seconds>.5f)return 0;
    for(i=0;i<p->modes;++i)if(!isfinite(p->mode[i].hz)||p->mode[i].hz<20||p->mode[i].hz>1000||
       !isfinite(p->mode[i].q)||p->mode[i].q<.3f||p->mode[i].q>8||
       !isfinite(p->mode[i].gain)||p->mode[i].gain<0||p->mode[i].gain>8)return 0;
    return 1;
}
int cb_profile_read(FILE *f,CbProfile *out) {
    CbProfile p={0};char tag[32],extra;unsigned version,i;
    if(!f||!out||fscanf(f,"%31s %u %u %f %f %f %f",tag,&version,&p.modes,&p.rise_shape,&p.fall_shape,
       &p.attack_seconds,&p.release_seconds)!=7||strcmp(tag,"VSL_CATCH_BLOOM")||version!=1||p.modes>CB_MAX_MODES)return 0;
    for(i=0;i<p.modes;++i)if(fscanf(f,"%f %f %f",&p.mode[i].hz,&p.mode[i].q,&p.mode[i].gain)!=3)return 0;
    if(fscanf(f," %c",&extra)==1||ferror(f)||!cb_profile_valid(&p))return 0;
    *out=p;return 1;
}
