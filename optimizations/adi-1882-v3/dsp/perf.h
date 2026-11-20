#ifndef VSL_PERF_H
#define VSL_PERF_H
#include <stdint.h>
#define VSL_PERF_COUNT 14
typedef struct {uint64_t exclusive,inclusive,calls;} VslPerfCounter;
#ifdef VSL_PROFILE
void vsl_perf_enter(unsigned id);
void vsl_perf_leave(void);
void vsl_perf_clear(void);
const VslPerfCounter *vsl_perf_get(void);
uint64_t vsl_perf_frequency(void);
#else
#define vsl_perf_enter(id) ((void)(id))
#define vsl_perf_leave() ((void)0)
#endif
/* Board profiling: supply an increasing64-bit cycle counter, no I/O here. */
#if defined(VSL_PROFILE) && !defined(_WIN32)
uint64_t vsl_board_cycle_count(void);
#endif
void vsl_source_perf_clear(void);
void vsl_source_perf_dump(const char *path);
#endif
