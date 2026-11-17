#include "event_synth/api.h"
#include "profiles.h"
#include <stdio.h>
#include <stdlib.h>
static EsPool pool;
int main(int argc,char **argv) {
    FILE *output;unsigned type,n,frames,count;EsFrame f;EsNotice notices[ES_LOG_CAPACITY];
    if(argc!=4){fputs("event_synth_probe TYPE FRAMES OUTPUT.f32\n",stderr);return 2;}
    type=(unsigned)atoi(argv[1]);frames=(unsigned)atoi(argv[2]);
    if(type>=ES_TYPES||frames>ES_RATE*30||!es_pool_init(&pool,vsl_event_profiles))return 2;
    EsRequest r={1,0,type,100,27431,1,1,1,1};
    if(!es_pool_start(&pool,&r))return 3;
    if(!(output=fopen(argv[3],"wb")))return 2;
    for(n=0;n<frames;++n) {
        es_pool_tick(&pool,&f);float sample=(float)f.sample[0];
        if(fwrite(&sample,sizeof sample,1,output)!=1){fclose(output);return 2;}
    }
    if(fclose(output))return 2;
    count=es_pool_notices(&pool,notices,ES_LOG_CAPACITY);
    printf("{\"frames\":%u,\"started\":%u,\"peak_active\":%u,\"notices\":[",frames,pool.started,pool.peak_active);
    for(n=0;n<count;++n)printf("%s{\"id\":%llu,\"frame\":%llu,\"action\":%u,\"reason\":%u}",n?",":"",
        (unsigned long long)notices[n].id,(unsigned long long)notices[n].frame,notices[n].action,notices[n].reason);
    puts("]}");return 0;
}
