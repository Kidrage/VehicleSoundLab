#include "file.h"
#include "atlas_take/parameters.h"
#include <stdlib.h>
#include <string.h>
#include <limits.h>
/* Explicit little endian fields; no pointers, padding or native structs on disk.
   FNV64 detects accidental damage, not malicious modification/authenticity. */
typedef struct {unsigned char *write;const unsigned char *read;size_t size,at;int ok;} Codec;
static void bytes(Codec *c,void *p,size_t n) {
    if(!c->ok||n>c->size-c->at){c->ok=0;return;}
    if(c->read)memcpy(p,c->read+c->at,n);else memcpy(c->write+c->at,p,n);
    c->at+=n;
}
static void u64(Codec *c,uint64_t *v,unsigned n) {
    unsigned char b[8]={0};unsigned i;
    if(!c->read)for(i=0;i<n;++i)b[i]=(unsigned char)(*v>>(8*i));
    bytes(c,b,n);
    if(c->read){*v=0;for(i=0;i<n;++i)*v|=(uint64_t)b[i]<<(8*i);}
}
static void natural(Codec *c,unsigned *v) {uint64_t n=*v;u64(c,&n,4);if(c->read)*v=(unsigned)n;}
static void integer(Codec *c,int *v) {unsigned n=(unsigned)*v;natural(c,&n);if(c->read){if(n>INT_MAX)c->ok=0;else *v=(int)n;}}
static void real(Codec *c,double *v) {uint64_t n=0;if(!c->read)memcpy(&n,v,8);u64(c,&n,8);if(c->read)memcpy(v,&n,8);}
static void reals(Codec *c,double *v,unsigned n) {unsigned i;for(i=0;i<n;++i)real(c,v+i);}
static void control(Codec *c,AdControl *p) {
    unsigned i,count;const AtField *f=at_fields(&count);
    for(i=0;i<count;++i){char *v=(char*)p+f[i].offset;if(f[i].integer)integer(c,(int*)v);else real(c,(double*)v);}
}
static void dna(Codec *c,SdProfile *p) {
    unsigned h,k;
    natural(c,&p->rate);natural(c,&p->window);natural(c,&p->hop);
    natural(c,&p->harmonics);natural(c,&p->components);real(c,&p->base_hz);
    if(p->harmonics>SD_MAX_HARMONICS||p->components>SD_MAX_COMPONENTS){c->ok=0;return;}
    reals(c,p->rho,p->components);
    for(h=0;h<p->harmonics;++h) {
        SdHarmonic *a=p->harmonic+h;reals(c,a->mean,4);
        for(k=0;k<p->components;++k)reals(c,a->basis[k],4);
        real(c,&a->rho);for(k=0;k<4;++k)reals(c,a->root[k],4);
    }
}
static void residual(Codec *c,RaBank *b) {
    unsigned i,h;natural(c,&b->count);if(b->count>RA_MAX_ANCHORS){c->ok=0;return;}
    for(i=0;i<b->count;++i) {
        SrProfile *p=b->profile+i;real(c,b->root+i);
        natural(c,&p->rate);natural(c,&p->bands);natural(c,&p->partials);
        if(p->bands>SR_MAX_BANDS){c->ok=0;return;}
        for(h=0;h<p->bands;++h) {
            SrBand *a=p->band+h;real(c,&a->low);real(c,&a->high);reals(c,a->power,2);reals(c,a->coherence,2);
        }
    }
}
static void payload(Codec *c,AtTake *t) {
    AtAssets *a=t->assets;unsigned i,h,has=a->config.residual_bank!=NULL;
    u64(c,&a->config.seed,8);integer(c,&a->config.profile);integer(c,&a->config.channels);
    real(c,&a->config.root_per_rpm);
    {int projection=(int)a->config.projection,route=(int)a->config.route;
        integer(c,&projection);integer(c,&route);if(c->read){a->config.projection=(DsProjection)projection;a->config.route=(DsRoute)route;}}
    natural(c,&has);natural(c,&a->bank.count);natural(c,&a->bank.harmonics);
    if(has>1||!a->bank.count||a->bank.count>SA_MAX_ANCHORS||a->bank.harmonics>SD_MAX_HARMONICS){c->ok=0;return;}
    for(i=0;i<a->bank.count&&c->ok;++i)dna(c,a->profile+i);
    for(i=0;i<a->bank.count;++i) {
        real(c,a->bank.offset+i);
        for(h=0;h<a->bank.harmonics;++h){reals(c,a->bank.phase[i][h],2);reals(c,a->bank.unit[i][h],4);}
        if(i)for(h=0;h<a->bank.harmonics;++h)reals(c,a->bank.delta[i-1][h],2);
    }
    reals(c,a->bank.sine,SA_TABLE_SIZE+1);
    if(has)residual(c,&a->residual);
    if(c->read)at_assets_bind(a,(int)has);
    control(c,&t->initial);u64(c,&t->frames,8);u64(c,&t->stop_frame,8);
    u64(c,&t->audio_hash,8);u64(c,&t->source_hash,8);natural(c,&t->count);
    if(t->count>t->capacity){c->ok=0;return;}
    for(i=0;i<t->count&&c->ok;++i){u64(c,&t->events[i].frame,8);control(c,&t->events[i].control);}
}
static uint64_t digest(const unsigned char *p,size_t n) {
    uint64_t h=AT_HASH_INITIAL;size_t i;for(i=0;i<n;++i){h^=p[i];h*=UINT64_C(1099511628211);}return h;
}
int at_take_encode(const AtTake *t,unsigned char **out,size_t *length) {
    Codec c={0};char magic[]="VSLRUN\r\n",identity[64];unsigned version=2,fields;uint64_t hash;
    if(!out||!length||!at_take_valid(t)||sizeof(double)!=8||sizeof(float)!=4)return 0;
    c.write=malloc(AT_FILE_LIMIT);if(!c.write)return 0;c.size=AT_FILE_LIMIT;c.ok=1;
    memcpy(identity,at_render_id(),64);bytes(&c,magic,8);natural(&c,&version);bytes(&c,identity,64);
    at_fields(&fields);natural(&c,&fields);
    /* Writer never mutates the source; codec field helpers share a traversal. */
    payload(&c,(AtTake*)t);hash=digest(c.write,c.at);u64(&c,&hash,8);
    if(!c.ok){free(c.write);return 0;}*out=c.write;*length=c.at;return 1;
}
int at_take_decode(AtTake *destination,const unsigned char *data,size_t length) {
    AtTake t={0};Codec c={0},tail={0};char magic[8],identity[64];unsigned version=0,fields=0,expected;uint64_t hash=0;int ok=0;
    if(!destination||!data||length<88||length>AT_FILE_LIMIT||sizeof(double)!=8||sizeof(float)!=4)return 0;
    tail.read=data+length-8;tail.size=8;tail.ok=1;u64(&tail,&hash,8);
    if(hash!=digest(data,length-8))return 0;
    c.read=data;c.size=length-8;c.ok=1;bytes(&c,magic,8);natural(&c,&version);bytes(&c,identity,64);
    natural(&c,&fields);at_fields(&expected);
    if(memcmp(magic,"VSLRUN\r\n",8)||version!=2||fields!=expected||memcmp(identity,at_render_id(),64)||!at_take_allocate(&t,AT_MAX_EVENTS))return 0;
    payload(&c,&t);
    if(!c.ok||c.at!=c.size||!at_take_valid(&t))goto done;
    at_take_free(destination);*destination=t;memset(&t,0,sizeof t);ok=1;
done:at_take_free(&t);return ok;
}
