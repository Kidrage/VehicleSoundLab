#define _CRT_SECURE_NO_WARNINGS
#include "stream.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
int main(int argc,char **argv) {
    DoModel m={0};DePlayer p;VslWavWriter w={0};double mono[257],pitch;float stereo[514];char *end;unsigned n,j,total=0;int ok=0;
    if(argc!=4)return 1;pitch=strtod(argv[3],&end);if(end==argv[3]||*end||!isfinite(pitch))return 1;
    if(!do_model_load(argv[1],&m)||!de_init(&p,&m,pitch,1,0)||!vsl_wav_begin_float(&w,argv[2],m.rate,2))goto done;
    while((n=de_process(&p,mono,257))!=0) {
        for(j=0;j<n;++j)stereo[2*j]=stereo[2*j+1]=(float)mono[j];
        if(!vsl_wav_write(&w,stereo,n))goto done;total+=n;
    }
    printf("DetailOSC1 | frames%u | relative_varispeed%.3f\n",total,pitch);ok=1;
done:if(w.file)ok=vsl_wav_end(&w)&&ok;do_model_free(&m);return ok?0:2;
}
