#define _CRT_SECURE_NO_WARNINGS
#include "perf.h"
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <stdio.h>
#endif
#ifdef VSL_PROFILE
typedef struct {unsigned id;uint64_t begin,children;} Level;
static Level stack[32];static unsigned depth;
static VslPerfCounter counters[VSL_PERF_COUNT];
static uint64_t now(void){
#ifdef _WIN32
 LARGE_INTEGER t;QueryPerformanceCounter(&t);return (uint64_t)t.QuadPart;
#else
 return vsl_board_cycle_count();
#endif
}
uint64_t vsl_perf_frequency(void){
#ifdef _WIN32
 LARGE_INTEGER f;QueryPerformanceFrequency(&f);return (uint64_t)f.QuadPart;
#else
 return 0; /* units are target cycles; convert using rendered sample count */
#endif
}
void vsl_perf_clear(void){depth=0;memset(counters,0,sizeof counters);}
const VslPerfCounter *vsl_perf_get(void){return counters;}
void vsl_perf_enter(unsigned id){Level *s;
 if(id==5){unsigned k;for(k=0;k<depth;++k)if(stack[k].id==8){id=13;break;}}
 s=stack+depth++;s->id=id;s->children=0;s->begin=now();}
void vsl_perf_leave(void){uint64_t end=now(),elapsed;Level *s=stack+--depth;
 elapsed=end-s->begin;counters[s->id].inclusive+=elapsed;
 counters[s->id].exclusive+=elapsed-s->children;++counters[s->id].calls;
 if(depth)stack[depth-1].children+=elapsed;
}
#endif
void vsl_source_perf_clear(void){
#ifdef VSL_PROFILE
 vsl_perf_clear();
#endif
}
void vsl_source_perf_dump(const char *path){
#if defined(VSL_PROFILE) && defined(_WIN32)
 unsigned i;FILE *f;if(!path)return;f=fopen(path,"wb");if(!f)return;
 fprintf(f,"id,exclusive_ticks,inclusive_ticks,calls,ticks_per_second\n");
 for(i=0;i<VSL_PERF_COUNT;++i)fprintf(f,"%u,%llu,%llu,%llu,%llu\n",i,
 (unsigned long long)counters[i].exclusive,(unsigned long long)counters[i].inclusive,
 (unsigned long long)counters[i].calls,(unsigned long long)vsl_perf_frequency());fclose(f);
#else
 (void)path;
#endif
}
