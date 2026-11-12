#include "models.h"
#include "rt_numeric/scope.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static RsmAssets assets,saved_assets;
static RsmRender a,b,saved;
static RssVoice source;
static float full[4096*2],chunked[4096*2],wide[512*12],stereo[512*2];
static float da[1024],db[1024],la[1024],lb[1024],ta[1024],tb[1024],dry[1024];
static int check_recipe(int selection) {
    RssConfig cfg;RsmControl p,bad;RsmCapture capture={da,la,ta,dry};unsigned n,k;
    CHECK(rsm_assets_load(&assets,selection));cfg=rsm_assets_config(&assets);p=rsm_assets_control(&assets);
    CHECK(rsm_render_init(&a,&cfg,2,&p));CHECK(rss_voice_init(&source,&cfg,&p.source));
    CHECK(rsm_render_process(&a,stereo,512,0,&capture));
    { RnScope scope=rn_scope_enter();
      for(n=0;n<512;++n) {
        RssFrame frame;double out[2];CHECK(rss_voice_tick(&source,&frame));
        CHECK(rss_output_frame(&a.layout,&frame,p.gain,p.width,out));
        for(k=0;k<2;++k) {
            float expected=(float)out[k];
            CHECK(dry[n*2+k]==expected);
            CHECK(stereo[n*2+k]==expected*(float)(n<480?n/480.:1));
            CHECK(da[n*2+k]==(float)frame.source.dna[k]);
            CHECK(la[n*2+k]==(float)frame.source.low[k]);CHECK(ta[n*2+k]==(float)frame.detail[k]);
        }
      }rn_scope_leave(scope);
    }
    saved=a;bad=p;bad.gain=NAN;CHECK(!rsm_render_set(&a,&bad));CHECK(!memcmp(&a,&saved,sizeof a));
    CHECK(!rsm_render_init(&a,&cfg,3,&p));CHECK(!memcmp(&a,&saved,sizeof a));
    if(!assets.has_low){bad=p;bad.source.source.low_gain=.1;CHECK(!rsm_render_set(&a,&bad));}
    if(!assets.has_detail){bad=p;bad.source.detail_gain=.1;CHECK(!rsm_render_set(&a,&bad));}
    CHECK(!memcmp(&a,&saved,sizeof a));
    /* Block partitioning cannot alter deterministic source or transport. */
    CHECK(rsm_render_init(&a,&cfg,2,&p));CHECK(rsm_render_init(&b,&cfg,2,&p));
    CHECK(rsm_render_process(&a,full,2048,0,NULL));
    for(n=0;n<2048;) {unsigned count=2048-n;if(count>137)count=137;
        CHECK(rsm_render_process(&b,chunked+n*2,count,0,NULL));n+=count;}
    CHECK(!memcmp(full,chunked,2048*2*sizeof(float)));
    p.source.source.pitch=.9;p.gain=.2;p.width=.4;
    CHECK(rsm_render_set(&a,&p));CHECK(rsm_render_set(&b,&p));
    CHECK(rsm_render_process(&a,full,2048,1,NULL));
    for(n=0;n<2048;){unsigned count=2048-n;if(count>173)count=173;
        CHECK(rsm_render_process(&b,chunked+n*2,count,n==0,NULL));n+=count;}
    CHECK(!memcmp(full,chunked,2048*2*sizeof(float)));CHECK(a.release==480&&b.release==480);
    for(n=480*2;n<4096;++n)CHECK(full[n]==0);
    CHECK(a.frame==4096&&b.frame==4096);CHECK(a.voice.source.frame==4096);
    /* 2/12 is one FL/FR observation bed, with identical source clocks/stems. */
    CHECK(rsm_render_init(&a,&cfg,2,&p));CHECK(rsm_render_init(&b,&cfg,12,&p));
    {RsmCapture ca={da,la,ta,NULL},cb={db,lb,tb,NULL};
     CHECK(rsm_render_process(&a,stereo,512,0,&ca));CHECK(rsm_render_process(&b,wide,512,0,&cb));}
    for(n=0;n<512;++n){CHECK(stereo[n*2]==wide[n*12]&&stereo[n*2+1]==wide[n*12+1]);for(k=2;k<12;++k)CHECK(wide[n*12+k]==0);}
    CHECK(!memcmp(da,db,sizeof da)&&!memcmp(la,lb,sizeof la)&&!memcmp(ta,tb,sizeof ta));
    CHECK(a.voice.source.dna.oscillator.phase==b.voice.source.dna.oscillator.phase);
    saved_assets=assets;CHECK(!rsm_assets_load(&assets,5));CHECK(!memcmp(&assets,&saved_assets,sizeof assets));
    return 0;
}
int main(void) {
    int i;for(i=0;i<5;++i)CHECK(!check_recipe(i));
    puts("PASS: five recipes, exact dry/stems, transport/reset, chunk partition, transactional controls and 2/12 routing");return 0;
}
