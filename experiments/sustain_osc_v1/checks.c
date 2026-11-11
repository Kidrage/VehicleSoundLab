#include "source.h"
#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#define PI 3.14159265358979323846
#define CHECK(x) do{if(!(x)){fprintf(stderr,"failed line%d: %s\n",__LINE__,#x);return 1;}}while(0)
int main(int argc,char **argv){SuModel *m=calloc(1,sizeof *m);SuSource *a=calloc(1,sizeof *a),*b=calloc(1,sizeof *b);double x[512*2],y[512*2];unsigned i,j;
    CHECK(argc==2&&m&&a&&b&&su_model_load(argv[1],m));
    CHECK(su_init(a,m,48271,1,1,1)&&su_init(b,m,48271,1,1,1));
    for(i=0;i<20;++i){su_process(a,x,512);su_process(b,y,257);su_process(b,y+514,255);
        for(j=0;j<1024;++j)CHECK(x[j]==y[j]&&isfinite(x[j]));}
    CHECK(!su_set(a,NAN,1,1)&&!su_set(a,1,1.1,1));CHECK(su_set(a,1.1,0,.5));
    su_process(a,x,1);CHECK(a->pitch>1&&a->pitch<1.001&&a->amount<1&&a->amount>.99);
    /* Independent analytic tone: constant known harmonic coefficients. */
    *m=(SuModel){0};m->rate=48000;m->window=1024;m->hop=256;m->harmonics=2;m->harmonic[0].mean[0]=.2;m->harmonic[1].mean[3]=.1;
    CHECK(su_init(a,m,1,1.1,0,1));
    for(i=0;i<8;++i){su_process(a,x,512);for(j=0;j<512;++j){double t=(i*512+j)*2*PI*1.1/1024;
        CHECK(fabs(x[2*j]-.2*cos(t))<1e-10&&fabs(x[2*j+1]+.1*sin(2*t))<1e-10);}}
    free(a);free(b);free(m);puts("SustainOSC1 analytic tone, seed/block invariance and smoothing checks pass");return 0;
}
