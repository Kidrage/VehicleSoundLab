#ifndef VSL_DSP_CONFIG_H
#define VSL_DSP_CONFIG_H
/* Fixed current V10 production recipe. These are capacities, not reductions
   of active orders, FIR lengths, noise streams or event voices. */
#ifdef VSL_FIXED_V10
#define SA_MAX_ANCHORS 1
#define SD_MAX_COMPONENTS 12
#define SF_MAX_BANDS 2
#define MT_MAX_MODES 13
#define MS_MAX_MODES 13
#define RDT_MAX_BANDS 8
#define SR_MAX_BANDS 1
#define SR_MAX_PARTIALS 1
/* Joint-channel resonance is absent from this recipe and rejected at setup. */
#define RVS_MAX_ORDER 1
#define RVS_MAX_BANDS 1
/* Dry source API has no room/IR/propagation renderer. */
#define VSL_MAX_IR 8
#define VSL_SPACE_DELAY 1
#define VSL_PATH_BUFFER 32
#define VSL_PATH_PHASES 1
#define VSL_DSP_FIR_SLOTS 8
#define VS_WORK_FRAMES 64
#endif
#endif
