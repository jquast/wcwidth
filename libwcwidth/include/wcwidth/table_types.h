/*
 * Table data model: the interval type, the terminal-override record layouts,
 * and the binary search over them.
 *
 * Hand-written.  The tables themselves -- every WCWIDTH_TABLE_* array, the
 * terminal override and alias arrays, and their entry counts -- are declared
 * in tables.h, which update-tables.py generates.
 */
#ifndef WCWIDTH_TABLE_TYPES_H
#define WCWIDTH_TABLE_TYPES_H

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

/*
 * Terminal override record layouts.
 *
 * The six single-codepoint categories are the merged override intervals;
 * grapheme clusters are stored as a flat codepoint pool with sorted lookup
 * entries.
 */
typedef struct
{
    const wcwidth_interval_t *narrower;
    size_t narrower_len;
    const wcwidth_interval_t *vs16_narrower;
    size_t vs16_narrower_len;
    const wcwidth_interval_t *vs15_wider;
    size_t vs15_wider_len;
    const wcwidth_interval_t *zeroer;
    size_t zeroer_len;
    const wcwidth_interval_t *narrow_wider;
    size_t narrow_wider_len;
    const wcwidth_interval_t *narrow_zeroer;
    size_t narrow_zeroer_len;
} wcwidth_override_set_t;

typedef struct
{
    uint32_t offset; /* into the table's grapheme codepoint pool */
    uint16_t len;    /* codepoints in the cluster */
    uint8_t width;   /* terminal-measured width */
} wcwidth_grapheme_entry_t;

typedef struct
{
    const char *name; /* canonical terminal name */
    const wcwidth_override_set_t *set;
    const uint32_t *grapheme_pool;
    size_t grapheme_pool_len;
    const wcwidth_grapheme_entry_t *grapheme_entries;
    size_t grapheme_entries_len;
} wcwidth_terminal_override_t;

typedef struct
{
    const char *alias;      /* TERM/TERM_PROGRAM value, lowercase */
    const char *canonical;  /* canonical terminal name */
} wcwidth_terminal_alias_t;

#ifdef __cplusplus
}
#endif

#endif /* WCWIDTH_TABLE_TYPES_H */
