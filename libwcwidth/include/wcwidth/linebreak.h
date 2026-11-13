/*
 * UAX #14 line breaking, the standard basis for word wrapping.  The class and auxiliary property
 * tables are declared in wcwidth/tables.h.
 *
 * https://www.unicode.org/reports/tr14/
 */
#ifndef WCWIDTH_LINEBREAK_H
#define WCWIDTH_LINEBREAK_H

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Return the UAX #14 line breaking class of *ucs*, one of the ``WCWIDTH_LB_*`` macros in
 * wcwidth/tables.h.  This is the raw property value; wcwidth_linebreak_breaks_u32() applies the
 * LB1 class resolution rules.
 */
unsigned wcwidth_linebreak_class(uint32_t ucs);

/*
 * Write the codepoint positions where a line may break into *breaks*.
 *
 * Positions are codepoint indices in [0, n].  Non-empty text always writes index n (LB3) and
 * skips index 0 (LB2); empty text writes nothing.
 *
 * *cps* and *breaks* must not be NULL when *n* is nonzero.  *mandatory* may be NULL to discard
 * the hard-break flags.
 *
 * With *hyphens* false, optional breaks after U+002D HYPHEN-MINUS, U+2010 HYPHEN and U+00AD SOFT
 * HYPHEN are omitted, matching Python's ``break_on_hyphens=False``.
 *
 * Returns the number of positions written, or (size_t) -1 when *cap* is too small or a memory
 * allocation fails.
 */
size_t wcwidth_linebreak_breaks_u32(const uint32_t *cps, size_t n, size_t *breaks,
                                    uint8_t *mandatory, size_t cap, bool hyphens);

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_LINEBREAK_H */
