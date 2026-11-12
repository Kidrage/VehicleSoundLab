#define _CRT_SECURE_NO_WARNINGS
#include "resonant_source/output.h"
#include "resonant_detail_io/profile.h"
#include "io/file.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
static SdProfile original,prepared,low;static RdtProfile detail;static RssVoice voice;
/* Portable offline host: each double row is output[layout], DNAraw L/R,
   LFraw L/R, calibrated LF L/R, detail L/R, mix L/R, source phase. */
int main(int argc,char **argv) {
    RssConfig cfg={0};RssControl ctl={{1,1,1,1,1,0},1};RssColour colour={0,1200,1900};
    SbLayout layout;unsigned frames,n,c;unsigned long long seed;FILE *file;char extra;
    if(argc!=10||sscanf(argv[5],"%lf %c",&colour.power_reduction,&extra)!=1||
       sscanf(argv[6],"%llu %c",&seed,&extra)!=1||sscanf(argv[7],"%u %c",&frames,&extra)!=1||
       !frames||frames>2880000||sscanf(argv[8],"%u %c",&c,&extra)!=1||!sb_layout_init(&layout,c)||
       sscanf(argv[9],"%lf %c",&ctl.source.pitch,&extra)!=1)return 2;
    if(!sd_profile_load(argv[1],&original)||!rss_profile_prepare(&prepared,&original,&colour))return 2;
    cfg.source.dna=&prepared;cfg.source.dna_seed=cfg.source.low_seed=48271;
    if(strcmp(argv[2],"-")) {if(!sd_profile_load(argv[2],&low))return 2;cfg.source.low=&low;}
    cfg.source.low_scale=1.6658265329883064;
    if(strcmp(argv[3],"-")) {if(!rdt_profile_load(argv[3],&detail))return 2;cfg.detail=&detail;}
    cfg.detail_seed=(uint64_t)seed;
    if(!rss_voice_init(&voice,&cfg,&ctl))return 2;
    file=vsl_fopen(argv[4],"wb");if(!file)return 3;
    for(n=0;n<frames;++n) {
        RssFrame f;double row[23];unsigned at=layout.channels;
        if(!rss_voice_tick(&voice,&f)||!rss_output_frame(&layout,&f,.5,1,row)){fclose(file);return 4;}
        for(c=0;c<2;++c)row[at++]=f.source.dna_raw[c];
        for(c=0;c<2;++c)row[at++]=f.source.low_raw[c];
        for(c=0;c<2;++c)row[at++]=f.source.low[c];
        for(c=0;c<2;++c)row[at++]=f.detail[c];
        for(c=0;c<2;++c)row[at++]=f.mix[c];
        row[at++]=f.phase_cycles;
        for(c=0;c<at;++c)if(!isfinite(row[c])){fclose(file);return 4;}
        if(fwrite(row,sizeof(double),at,file)!=at){fclose(file);return 3;}
    }
    if(fclose(file))return 3;
    printf("frames=%u layout=%u record_columns=%u\n",frames,layout.channels,layout.channels+11);return 0;
}
