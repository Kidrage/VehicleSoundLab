#ifndef VSL_DNA_TABLE_STATE_H
#define VSL_DNA_TABLE_STATE_H
#define SA_TABLE_POINTS 2048
#ifndef VSL_DNA_TABLE_HOP
#define VSL_DNA_TABLE_HOP 128
#endif
#if VSL_DNA_TABLE_HOP < 16 || VSL_DNA_TABLE_HOP > 256 || (VSL_DNA_TABLE_HOP & (VSL_DNA_TABLE_HOP-1))
#error VSL_DNA_TABLE_HOP must be a power of two from16 through256
#endif
#define SA_TABLE_HOP VSL_DNA_TABLE_HOP
typedef struct {float re,im;} SaTableComplex;
typedef struct {
    SaTableComplex main[2][SA_TABLE_POINTS],body[2][SA_TABLE_POINTS];
    SaTableComplex work[SA_TABLE_POINTS],temporary[SA_TABLE_POINTS];
    SaTableComplex roots[SA_TABLE_POINTS/2];
    float coefficients[320][4],weights[320];
    int ready,has_body;
} SaTable;
/* Per-engine, reentrant state; initialize before audio processing. */
void sa_table_init(SaTable *table);
#endif
