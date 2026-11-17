/* Authoring-only bridge. Uses the same event pool as the vehicle source. */
#include "event_synth/api.h"
#include <stddef.h>
#include <string.h>
#ifdef _WIN32
#define EA_API __declspec(dllexport)
#else
#define EA_API
#endif
EA_API unsigned vsl_event_author_abi(void){return 4;}
EA_API unsigned vsl_event_author_profile_size(void){return (unsigned)sizeof(EsProfile);}
EA_API unsigned vsl_event_author_request_size(void){return (unsigned)sizeof(EsRequest);}
EA_API int vsl_event_author_render(const EsProfile *profile,const EsRequest *request,
                                  unsigned frames,unsigned release_frame,float *output) {
    EsPool pool;EsProfile bank[ES_TYPES];EsFrame frame;unsigned n,k;
    if(!profile||!request||!output||!frames||frames>12*ES_RATE||
       !es_profile_valid(profile)||request->type>=ES_TYPES||request->requested_frame)return 0;
    for(k=0;k<ES_TYPES;++k) {
        memset(bank+k,0,sizeof bank[k]);bank[k].duration_seconds=.005;bank[k].release_seconds=.001;
    }
    bank[request->type]=*profile;
    if(!es_pool_init(&pool,bank)||es_pool_start(&pool,request)!=1)return 0;
    for(n=0;n<frames;++n) {
        if(n==release_frame)es_pool_release(&pool,(int)request->type,profile->release_seconds);
        if(!es_pool_tick(&pool,&frame))return 0;
        output[n]=(float)frame.sample[0];
    }
    return 1;
}
