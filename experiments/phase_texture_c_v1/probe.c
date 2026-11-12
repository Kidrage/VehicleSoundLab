#define _CRT_SECURE_NO_WARNINGS
#include "dna_scene/source.h"
#include "io/wav.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static SdProfile dna,low;static DsSource source;
int main(int argc,char **argv) {
    DsSourceConfig config={0};DsSourceControl control={1,1,1,1,1,0};
    VslWavWriter writers[3]={{0}};const char *names[]={"dna","low","mix"};
    unsigned frames,n,i;char path[4096];FILE *motion;
    if(argc!=8||!sd_profile_load(argv[1],&dna)||!sd_profile_load(argv[2],&low))return 2;
    control.phase_texture=strtod(argv[3],NULL);control.pitch=strtod(argv[4],NULL);
    {double seconds=strtod(argv[5],NULL);if(!isfinite(seconds)||seconds<=0||seconds>120)return 2;frames=(unsigned)(seconds*48000);}
    config.dna=&dna;config.low=&low;config.dna_seed=config.low_seed=48271;
    config.phase_seed=(uint64_t)strtoull(argv[6],NULL,10);config.low_scale=1.6658265329883064;
    if(!ds_source_init(&source,&config,&control))return 2;
    for(i=0;i<3;++i) {snprintf(path,sizeof path,"%s/%s.wav",argv[7],names[i]);if(!vsl_wav_begin_float(&writers[i],path,48000,2))return 3;}
    snprintf(path,sizeof path,"%s/motion.f64",argv[7]);motion=vsl_fopen(path,"wb");if(!motion)return 3;
    for(n=0;n<frames;++n) {
        DsSourceFrame f;float raw[3][2];ds_source_tick(&source,&f);
        for(i=0;i<2;++i) {raw[0][i]=(float)f.dna_raw[i];raw[1][i]=(float)f.low_raw[i];raw[2][i]=(float)(.5*(f.dna[i]+f.low[i]));}
        for(i=0;i<3;++i)if(!vsl_wav_write(&writers[i],raw[i],1))return 3;
        if(fwrite(&source.phase.motion.last_seconds,sizeof(double),1,motion)!=1)return 3;
    }
    for(i=0;i<3;++i)if(!vsl_wav_end(&writers[i]))return 3;
    if(fclose(motion))return 3;return 0;
}
