#include <stddef.h>
#include "parameters.h"
#include <math.h>
#include <string.h>
#define I(f) {#f,offsetof(VslParams,f),1},
#define D(f) {#f,offsetof(VslParams,f),0},
static const VslParamField fields[]={VSL_TAKE_FIELDS(I,D)};
#undef I
#undef D
const VslParamField *vsl_take_fields(unsigned *count) { *count=(unsigned)(sizeof fields/sizeof fields[0]);return fields; }
int vsl_params_same(const VslParams *a,const VslParams *b) {
    unsigned n,i;const VslParamField *f=vsl_take_fields(&n);
    for(i=0;i<n;++i) {
        const char *aa=(const char*)a+f[i].offset,*bb=(const char*)b+f[i].offset;
        if(f[i].integer?*(const int*)aa!=*(const int*)bb:*(const double*)aa!=*(const double*)bb)return 0;
    }
    return 1;
}
int vsl_take_params_valid(const VslParams *p) {
    unsigned i,n;const VslParamField *f=vsl_take_fields(&n);
    for(i=0;i<n;++i) {
        const char *at=(const char*)p+f[i].offset;
        if(f[i].integer) {
            int v=*(const int*)at,hi=1;
            if(!strcmp(f[i].name,"profile"))hi=VSL_PROFILE_COUNT-1;
            else if(!strcmp(f[i].name,"drive_mode"))hi=VSL_AUTODRIVE;
            else if(!strcmp(f[i].name,"gear"))hi=7;
            else if(!strcmp(f[i].name,"firing_source"))hi=VSL_SOURCE_VARIABLE;
            else if(!strcmp(f[i].name,"start_id")) { if(v<0)return 0;continue; }
            if(v<0||v>hi)return 0;
        } else {
            double v=*(const double*)at,lo=0,hi=1;
            if(!strcmp(f[i].name,"rpm"))hi=10000;
            else if(!strcmp(f[i].name,"load"))lo=-1;
            else if(!strcmp(f[i].name,"release_time")) { lo=.08;hi=1.2; }
            if(!isfinite(v)||v<lo||v>hi)return 0;
        }
    }
    return 1;
}
