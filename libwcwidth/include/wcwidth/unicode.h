/*
 * Shared Unicode codepoint classification for the cluster/override loops.
 *
 * Internal header: static inline predicates used by wcswidth.c, wcstwidth.c,
 * width.c, terminal_override.c, and grapheme.c.  All codepoint data comes
 * from the generated tables, never hand-maintained copies.
 */
#ifndef WCWIDTH_UNICODE_H
#define WCWIDTH_UNICODE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "wcwidth/tables.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Virama conjunct: IndicSyllabicCategory Virama or Invisible_Stacker. */
static inline bool
wcwidth_is_virama(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, WCWIDTH_ISC_VIRAMA, WCWIDTH_ISC_VIRAMA_LEN) != 0
           || wcwidth_bisearch(ucs, WCWIDTH_ISC_INVISIBLE_STACKER,
                               WCWIDTH_ISC_INVISIBLE_STACKER_LEN)
                  != 0;
}

static inline bool
wcwidth_is_regional_indicator(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, WCWIDTH_GRAPHEME_REGIONAL_INDICATOR,
                            WCWIDTH_GRAPHEME_REGIONAL_INDICATOR_LEN)
           != 0;
}

static inline bool
wcwidth_is_extended_pictographic(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, WCWIDTH_EXTENDED_PICTOGRAPHIC,
                            WCWIDTH_EXTENDED_PICTOGRAPHIC_LEN)
           != 0;
}

/* Base character eligible for ZWJ grapheme overrides: ExtPict or RI. */
static inline bool
wcwidth_is_emoji_zwj_set(uint32_t ucs)
{
    return wcwidth_is_extended_pictographic(ucs) || wcwidth_is_regional_indicator(ucs);
}

static inline bool
wcwidth_is_fitzpatrick(uint32_t ucs)
{
    return ucs >= 0x1F3FB && ucs <= 0x1F3FF;
}

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_UNICODE_H */
