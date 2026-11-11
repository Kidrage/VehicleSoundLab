#define _CRT_SECURE_NO_WARNINGS
#include "source.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
#include <inttypes.h>
int main(int argc,char **argv) {
    SuModel *m=NULL;SuSource *p=NULL;VslWavWriter w={0};double x[257*2],seconds,pitch,amount;uint64_t frames,i=0,seed;float f[257*2];unsigned n,j;char *end;int ok=0;clock_t start;
    if(argc!=7&&argc!=8)return 1;
    seconds=strtod(argv[3],&end);if(end==argv[3]||*end||!isfinite(seconds)||seconds<=0||seconds>60)return 1;
    pitch=strtod(argv[4],&end);if(end==argv[4]||*end)return 1;
    amount=strtod(argv[5],&end);if(end==argv[5]||*end)return 1;
    seed=strtoull(argv[6],&end,10);if(end==argv[6]||*end)return 1;
    m=calloc(1,sizeof *m);p=calloc(1,sizeof *p);if(!m||!p||!su_model_load(argv[1],m)||!su_init(p,m,seed,pitch,amount,1))goto done;
    if(!vsl_wav_begin_float(&w,argv[2],m->rate,2))goto done;frames=(uint64_t)floor(seconds*m->rate+.5);start=clock();
    while(i<frames){uint64_t left=frames-i,change=frames/2;n=(unsigned)(left>257?257:left);
        if(argc==8){if(i==change)su_set(p,1.1,amount,1);if(i<change&&n>change-i)n=(unsigned)(change-i);}
        su_process(p,x,n);for(j=0;j<n*2;++j){if(!isfinite(x[j]))goto done;f[j]=(float)x[j];}
        if(!vsl_wav_write(&w,f,n))goto done;i+=n;
    }
    printf("SustainOSC1 | frames%" PRIu64 " | seed%" PRIu64 " | updates%" PRIu64 " | CPU_seconds%.6f\n",i,seed,p->updates,(clock()-start)/(double)CLOCKS_PER_SEC);ok=1;
done:if(w.file)ok=vsl_wav_end(&w)&&ok;free(p);free(m);return ok?0:2;
}
