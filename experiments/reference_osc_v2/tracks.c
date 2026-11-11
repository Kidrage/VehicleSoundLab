#define _CRT_SECURE_NO_WARNINGS
#include "tracks.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <inttypes.h>
#define RT_PI 3.14159265358979323846
void rt_tracks_free(RtTracks *t) {
    if(!t)return;free(t->offsets);free(t->ids);memset(t,0,sizeof *t);
}
static int join(const RoPartial *a,const RoPartial *b,double duration) {
    unsigned c;if(a->group!=b->group)return 0;
    for(c=0;c<2;++c) {
        const RoChannel *x=&a->channel[c],*y=&b->channel[c];
        double phase=x->phase0+x->omega0*duration+x->c2*duration*duration+x->c3*duration*duration*duration;
        double omega=x->omega0+2*x->c2*duration+3*x->c3*duration*duration;
        if(fabs(x->amplitude1-y->amplitude0)>1e-9||fabs(remainder(phase-y->phase0,2*RT_PI))>1e-8||fabs(omega-y->omega0)>1e-6)return 0;
    }
    return 1;
}
int rt_tracks_load(const char *path,const RoModel *model,RtTracks *tracks) {
    FILE *f=NULL;RtTracks t={0};const RoPartial **last=NULL;unsigned *seen=NULL,*lengths=NULL;
    uint64_t *ends=NULL;char tag[32],tail[2];unsigned version,i,j,id,k=0,distinct=0,total=0;int ok=0;
    if(!path||!model||!model->segments||!tracks)return 0;
    for(i=0;i<model->count;++i)total+=model->segments[i].count;
    f=fopen(path,"rb");if(!f)return 0;
    if(fscanf(f,"%31s %u %u %u %u",tag,&version,&t.segments,&t.tracks,&t.rows)!=5||
       strcmp(tag,"VSL_OSC_IDS")||version!=1||t.segments!=model->count||
       !t.tracks||t.tracks>RT_MAX_TRACKS||t.rows!=total||!total)goto done;
    t.offsets=calloc((size_t)t.segments+1,sizeof *t.offsets);t.ids=calloc(t.rows,sizeof *t.ids);
    last=calloc(t.tracks,sizeof *last);seen=calloc(t.tracks,sizeof *seen);
    ends=calloc(t.tracks,sizeof *ends);lengths=calloc(t.tracks,sizeof *lengths);
    if(!t.offsets||!t.ids||!last||!seen||!ends||!lengths)goto done;
    for(i=0;i<t.segments;++i) {
        const RoSegment *s=&model->segments[i];uint64_t start;unsigned frames,rows;
        t.offsets[i]=k;
        if(fscanf(f,"%" SCNu64 " %u %u",&start,&frames,&rows)!=3||start!=s->start||frames!=s->frames||rows!=s->count)goto done;
        for(j=0;j<s->count;++j) {
            if(fscanf(f,"%u",&id)!=1||id>=t.tracks||seen[id]==i+1)goto done;
            if(last[id]) {
                if(ends[id]!=s->start||!join(last[id],&s->partials[j],lengths[id]/(double)model->rate))goto done;
            } else ++distinct;
            t.ids[k++]=id;seen[id]=i+1;last[id]=&s->partials[j];ends[id]=s->start+s->frames;lengths[id]=s->frames;
        }
    }
    t.offsets[t.segments]=k;
    if(distinct!=t.tracks||k!=t.rows||fscanf(f,"%1s",tail)==1||ferror(f))goto done;
    rt_tracks_free(tracks);*tracks=t;memset(&t,0,sizeof t);ok=1;
done:
    free(last);free(seen);free(ends);free(lengths);rt_tracks_free(&t);fclose(f);return ok;
}
