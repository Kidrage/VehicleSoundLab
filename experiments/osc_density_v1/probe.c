#include "oscillator.h"
#include "io/wav.h"
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
int main(int argc,char **argv) {
    DoModel m={0};VslWavWriter w={0};double *mono=NULL;float block[512*2];unsigned i,j;int ok=0;clock_t begin;
    if(argc!=3)return 1;
    if(!do_model_load(argv[1],&m))goto done;
    mono=calloc(m.frames,sizeof *mono);if(!mono)goto done;begin=clock();
    if(!do_render(&m,mono)||!vsl_wav_begin_float(&w,argv[2],m.rate,2))goto done;
    for(i=0;i<m.frames;i+=512) {
        unsigned count=m.frames-i<512?m.frames-i:512;
        for(j=0;j<count;++j)block[2*j]=block[2*j+1]=(float)mono[i+j];
        if(!vsl_wav_write(&w,block,count))goto done;
    }
    printf("DenseOSC1 | frames%u | window%u | hop%u | grains%u | CPU_seconds%.6f\n",
           m.frames,m.window,m.hop,m.count,(clock()-begin)/(double)CLOCKS_PER_SEC);ok=1;
done:
    if(w.file)ok=vsl_wav_end(&w)&&ok;
    free(mono);do_model_free(&m);return ok?0:2;
}
