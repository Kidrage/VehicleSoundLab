#define _CRT_SECURE_NO_WARNINGS
#include "pitch.h"
#include "oscillator.h"
#include <stdio.h>
#include <math.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do{if(!(x)){fprintf(stderr,"FAIL: %s\n",m);++failures;}}while(0)
#define PI 3.14159265358979323846
static void loader_checks(RoModel *model) {
    const char *file="tracked_osc_ids_test.txt";RtTracks t={0};unsigned *saved;FILE *f;
    const char *bad[]={"VSL_OSC_IDS 1 2 1 2\n0 24000 1\n0\n24000 24000 1\n1\n",
        "VSL_OSC_IDS 1 2 2 2\n0 24000 1\n0\n24000 24000 1\n0\n",
        "VSL_OSC_IDS 1 2 1 2\n0 24000 1\n0\n24000 24000 1\n0\nextra"};unsigned i;
    f=fopen(file,"wb");CHECK(f!=NULL,"sidecar fixture opens");if(!f)return;
    fputs("VSL_OSC_IDS 1 2 1 2\n0 24000 1\n0\n24000 24000 1\n0\n",f);fclose(f);
    CHECK(rt_tracks_load(file,model,&t),"continuous track joins load");saved=t.ids;
    for(i=0;i<sizeof bad/sizeof bad[0];++i){f=fopen(file,"wb");if(!f)break;fputs(bad[i],f);fclose(f);
        CHECK(!rt_tracks_load(file,model,&t)&&t.ids==saved,"bad sidecar preserves active IDs");}
    model->segments[1].partials[0].channel[0].phase0+=.1;
    f=fopen(file,"wb");if(f){fputs("VSL_OSC_IDS 1 2 1 2\n0 24000 1\n0\n24000 24000 1\n0\n",f);fclose(f);}
    CHECK(!rt_tracks_load(file,model,&t),"phase-discontinuous ID reuse rejects");
    model->segments[1].partials[0].channel[0].phase0-=.1;
    rt_tracks_free(&t);remove(file);
}
int main(void) {
    RoPartial parts[2]={0};RoSegment segments[2]={{0,24000,1,&parts[0]},{24000,24000,1,&parts[1]}};
    RoModel model={48000,2,48000,segments};unsigned offsets[3]={0,1,2},ids[2]={0,0};RtTracks tracks={1,2,2,offsets,ids};
    RtPlayer a={0},b={0};RoPlayer original;double x[514],y[514],ref[514],error=0;unsigned i,c,n,frame=0;
    parts[0].channel[0]=(RoChannel){.1,.15,.37,2*PI*223.7,PI*31,0};parts[0].channel[1]=parts[0].channel[0];parts[0].channel[1].phase0+=1.2;
    for(c=0;c<2;++c){parts[1].channel[c]=parts[0].channel[c];parts[1].channel[c].amplitude0=.15;parts[1].channel[c].amplitude1=.2;
        parts[1].channel[c].phase0+=2*PI*223.7*.5+PI*31*.25;parts[1].channel[c].omega0+=2*PI*31*.5;}
    CHECK(rt_player_init(&a,&model,&tracks,1,0)&&ro_player_init(&original,&model,0),"unity players initialize");
    while(frame<48000){n=48000-frame;if(n>257)n=257;rt_process(&a,x,n);ro_process(&original,ref,NULL,n);
        CHECK(!memcmp(x,ref,n*2*sizeof(double)),"unity pitch is exact V1 across segment joins");frame+=n;}
    rt_player_free(&a);frame=0;
    CHECK(rt_player_init(&a,&model,&tracks,1.25,0)&&rt_player_init(&b,&model,&tracks,1.25,0),"transposed players initialize");
    while(frame<48000){n=48000-frame;if(n>257)n=257;CHECK(rt_process(&a,x,n)==n,"full block renders");
        for(i=0;i<n;++i){double t=(frame+i)/48000.;rt_process(&b,y+i*2,1);
            error=fmax(error,fabs(x[i*2]-(.1+.1*t)*cos(.37+1.25*(2*PI*223.7*t+PI*31*t*t))));}
        CHECK(!memcmp(x,y,n*2*sizeof(double)),"pitch preserves exact host-block independence");frame+=n;}
    CHECK(error<1e-8,"independent transposed AM/chirp formula with unchanged duration");
    CHECK(!rt_process(&a,x,1),"bounded end");rt_player_free(&a);rt_player_free(&b);
    rt_player_init(&a,&model,&tracks,1,0);rt_set(&a,1.2,.5);rt_process(&a,x,1);
    CHECK(a.pitch>1&&a.pitch<1.001&&a.high>0&&a.high<.001,"live pitch/high targets smooth without phase reset");
    CHECK(!rt_set(&a,NAN,0)&&!rt_set(&a,1.26,0)&&!rt_set(&a,1,-1),"invalid targets reject");rt_player_free(&a);
    loader_checks(&model);
    printf("TrackedOSC2 checks: analytic pitch error %.3g, failures%d\n",error,failures);return failures?1:0;
}
