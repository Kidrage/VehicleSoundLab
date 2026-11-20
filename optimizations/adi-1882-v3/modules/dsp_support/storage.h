#ifndef VSL_DSP_STORAGE_H
#define VSL_DSP_STORAGE_H
#include <stdlib.h>
#include <string.h>

/* DSP: one synthesizer, retaining the original per-object algorithm limits.
   Four spectral banks/voices and twelve FIRs cover the current V10 incl. flare.
   Exhaustion fails creation; destroy returns slots for the next initialization.
   Initialization/destruction are serialized by the caller, outside audio.
   Desktop builds retain their original heap allocation and instance count. */
#ifndef VSL_DSP_SPECTRAL_SLOTS
#define VSL_DSP_SPECTRAL_SLOTS 4
#endif
#ifndef VSL_DSP_FIR_SLOTS
#define VSL_DSP_FIR_SLOTS 12
#endif

#define VSL_STRINGIFY_INNER(x) #x
#define VSL_STRINGIFY(x) VSL_STRINGIFY_INNER(x)
#if defined(VSL_DSP_STATIC) && defined(VSL_ADSP_21569)
#define VSL_SECTION(name) _Pragma(VSL_STRINGIFY(section(name, ZERO_INIT)))
#else
#define VSL_SECTION(name)
#endif
#define VSL_L1_STATE "seg_vsl_l1_state"
#define VSL_L1_VOICE "seg_vsl_l1_voice"
#define VSL_L2_HISTORY "seg_vsl_l2_history"
#define VSL_L1_FIR "seg_vsl_l1_fir"
#define VSL_DDR "seg_sdram_bsz_data"

#ifdef VSL_DSP_STATIC
#define VSL_INIT_WORK static
#define VSL_STORAGE(name,type,count,section_name) \
    VSL_SECTION(section_name) static type name##_slots[count]; \
    static unsigned char name##_used[count]; \
    static type *name##_acquire(void) { \
        unsigned slot; \
        for(slot=0;slot<(count);++slot)if(!name##_used[slot]) { \
            name##_used[slot]=1; \
            memset(&name##_slots[slot],0,sizeof name##_slots[slot]); \
            return &name##_slots[slot]; \
        } \
        return NULL; \
    } \
    static void name##_release(type *object) { \
        unsigned slot;if(!object)return; \
        for(slot=0;slot<(count);++slot)if(object==&name##_slots[slot]) { \
            name##_used[slot]=0;return; \
        } \
    }
#else
#define VSL_INIT_WORK
#define VSL_STORAGE(name,type,count,section_name) \
    static type *name##_acquire(void) {return calloc(1,sizeof(type));} \
    static void name##_release(type *object) {free(object);}
#endif
#endif
