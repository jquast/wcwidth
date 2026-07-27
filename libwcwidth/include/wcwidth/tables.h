/*
 * Binary search in Unicode interval tables.
 *
 * Port of wcwidth/bisearch.py.
 */
#ifndef WCWIDTH_TABLES_H
#define WCWIDTH_TABLES_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * An interval [start, end] (inclusive) in Unicode codepoint space.
 */
typedef struct
{
    uint32_t start;
    uint32_t end;
} wcwidth_interval_t;

/*
 * Binary search for *ucs* in a sorted interval table.
 *
 * Returns 1 if *ucs* is contained within any interval in *table*, 0 otherwise.
 *
 * *table* must be sorted ascending, with non-overlapping intervals.
 */
int wcwidth_bisearch(uint32_t ucs, const wcwidth_interval_t *table, size_t table_len);

extern const wcwidth_interval_t WCWIDTH_TABLE_WIDE[];
extern const size_t WCWIDTH_TABLE_WIDE_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_ZERO[];
extern const size_t WCWIDTH_TABLE_ZERO_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_AMBIGUOUS[];
extern const size_t WCWIDTH_TABLE_AMBIGUOUS_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_EXTEND[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_EXTEND_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_L[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_L_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_V[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_V_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_T[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_T_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_LV[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_LV_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_LVT[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_LVT_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_PREPEND[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_PREPEND_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_SPACINGMARK[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_SPACINGMARK_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_CONTROL[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_CONTROL_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_GRAPHEME_REGIONAL_INDICATOR[];
extern const size_t WCWIDTH_TABLE_GRAPHEME_REGIONAL_INDICATOR_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_EXTENDED_PICTOGRAPHIC[];
extern const size_t WCWIDTH_TABLE_EXTENDED_PICTOGRAPHIC_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_INCB_LINKER[];
extern const size_t WCWIDTH_TABLE_INCB_LINKER_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_INCB_CONSONANT[];
extern const size_t WCWIDTH_TABLE_INCB_CONSONANT_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_INCB_EXTEND[];
extern const size_t WCWIDTH_TABLE_INCB_EXTEND_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_MC[];
extern const size_t WCWIDTH_TABLE_MC_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_VS15[];
extern const size_t WCWIDTH_TABLE_VS15_LEN;

extern const wcwidth_interval_t WCWIDTH_TABLE_VS16[];
extern const size_t WCWIDTH_TABLE_VS16_LEN;

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_TABLES_H */
