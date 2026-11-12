#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include <math.h>
#include <string.h>
int st_profile_valid(const StProfile *p) {
    return p && sr_profile_valid(&p->spectrum) &&
        isfinite(p->attack_seconds) && p->attack_seconds >= 1./48000 && p->attack_seconds <= .5 &&
        isfinite(p->release_seconds) && p->release_seconds >= 1./48000 && p->release_seconds <= 2;
}
int st_profile_read(FILE *f, StProfile *out) {
    StProfile p={0};char tag[32];unsigned version;
    if(!f||!out||fscanf(f,"%31s %u %lf %lf",tag,&version,&p.attack_seconds,&p.release_seconds)!=4||
       strcmp(tag,"VSL_START_TEXTURE")||version!=1||!sr_profile_read(f,&p.spectrum)||!st_profile_valid(&p))return 0;
    *out=p;return 1;
}
