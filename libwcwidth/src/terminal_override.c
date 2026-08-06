/*
 * Terminal override lookup.
 *
 * Resolves a terminal identifier to its generated override tables and looks up
 * grapheme cluster overrides (src/tables/table_terminal_overrides.c).
 */
#include "wcwidth/terminal_override.h"
#include "wcwidth/generated_tables.h"
#include "wcwidth/unicode.h"
#include "wcwidth/utf8.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define MAX_TERM_NAME_LEN 64

static bool
is_ascii_space(char c)
{
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v';
}

static char
ascii_lower(char c)
{
    if (c >= 'A' && c <= 'Z') {
        return (char) (c + 32);
    }
    return c;
}

static const wcwidth_terminal_override_t *
find_terminal(const char *name)
{
    size_t lo = 0;
    size_t hi = WCWIDTH_TERMINAL_OVERRIDES_LEN;

    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        int cmp = strcmp(name, WCWIDTH_TERMINAL_OVERRIDES[mid].name);
        if (cmp == 0) {
            return &WCWIDTH_TERMINAL_OVERRIDES[mid];
        }
        if (cmp < 0) {
            hi = mid;
        }
        else {
            lo = mid + 1;
        }
    }
    return NULL;
}

const wcwidth_terminal_override_t *
wcwidth_resolve_terminal(const char *term_program)
{
    const char *p;
    const char *end;
    char buf[MAX_TERM_NAME_LEN];
    size_t n = 0;
    size_t lo;
    size_t hi;

    if (term_program == NULL || term_program[0] == '\0') {
        return NULL;
    }

    /* Skip surrounding whitespace and lowercase; all real identifiers are
     * ASCII. */
    p = term_program;
    while (is_ascii_space(*p)) {
        p++;
    }
    end = p + strlen(p);
    while (end > p && is_ascii_space(end[-1])) {
        end--;
    }
    if (end - p >= (ptrdiff_t) sizeof(buf)) {
        return NULL; /* far longer than any terminal name */
    }
    for (; p < end; p++) {
        buf[n++] = ascii_lower(*p);
    }
    buf[n] = '\0';

    /* Alias lookup (sorted by alias). */
    lo = 0;
    hi = WCWIDTH_TERMINAL_ALIASES_LEN;
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        int cmp = strcmp(buf, WCWIDTH_TERMINAL_ALIASES[mid].alias);
        if (cmp == 0) {
            return find_terminal(WCWIDTH_TERMINAL_ALIASES[mid].canonical);
        }
        if (cmp < 0) {
            hi = mid;
        }
        else {
            lo = mid + 1;
        }
    }

    /* Canonical name lookup (sorted by name); unknown names get no overrides. */
    return find_terminal(buf);
}

int
wcwidth_grapheme_override_lookup(const wcwidth_terminal_override_t *term, const uint32_t *cps,
                                 size_t len)
{
    size_t lo = 0;
    size_t hi = term->grapheme_entries_len;

    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        const wcwidth_grapheme_entry_t *entry = &term->grapheme_entries[mid];
        const uint32_t *entry_cps = term->grapheme_pool + entry->offset;
        size_t common = len < entry->len ? len : (size_t) entry->len;
        size_t i;
        int cmp = 0;

        for (i = 0; i < common; i++) {
            if (cps[i] != entry_cps[i]) {
                cmp = cps[i] < entry_cps[i] ? -1 : 1;
                break;
            }
        }
        if (cmp == 0 && len != entry->len) {
            cmp = len < entry->len ? -1 : 1;
        }
        if (cmp == 0) {
            return entry->width;
        }
        if (cmp < 0) {
            hi = mid;
        }
        else {
            lo = mid + 1;
        }
    }
    return -1;
}

static bool
is_grapheme_extend(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_EXTEND, WCWIDTH_TABLE_GRAPHEME_EXTEND_LEN)
           != 0;
}

size_t
wcwidth_scan_zwj_cluster_end(const uint32_t *cp, size_t n, size_t start)
{
    size_t idx = start + 1;

    /* Skip Extend characters (Fitzpatrick modifiers, etc.) before the first ZWJ. */
    while (idx < n && is_grapheme_extend(cp[idx])) {
        idx++;
    }
    /* Follow ZWJ chains: ExtPict Extend* ZWJ x ExtPict (GB11). */
    while (idx < n) {
        if (cp[idx] != 0x200D) {
            break;
        }
        idx++;
        if (idx < n && wcwidth_is_emoji_zwj_set(cp[idx])) {
            idx++;
            while (idx < n && is_grapheme_extend(cp[idx])) {
                idx++;
            }
            continue;
        }
        break;
    }
    return idx;
}

size_t
wcwidth_scan_zwj_cluster_end_u8(const char *utf8, size_t n, size_t start)
{
    size_t idx = start;
    uint32_t cp;

    /* Skip the base character itself. */
    idx += wcwidth_utf8_decode_single(utf8 + idx, n - idx, &cp);

    /* Skip Extend characters before the first ZWJ. */
    while (idx < n) {
        size_t consumed = wcwidth_utf8_decode_single(utf8 + idx, n - idx, &cp);
        if (!is_grapheme_extend(cp)) {
            break;
        }
        idx += consumed;
    }
    /* Follow ZWJ chains (GB11). */
    while (idx < n) {
        size_t consumed = wcwidth_utf8_decode_single(utf8 + idx, n - idx, &cp);
        if (cp != 0x200D) {
            break;
        }
        idx += consumed;
        if (idx < n) {
            consumed = wcwidth_utf8_decode_single(utf8 + idx, n - idx, &cp);
            if (wcwidth_is_emoji_zwj_set(cp)) {
                idx += consumed;
                while (idx < n) {
                    consumed = wcwidth_utf8_decode_single(utf8 + idx, n - idx, &cp);
                    if (!is_grapheme_extend(cp)) {
                        break;
                    }
                    idx += consumed;
                }
                continue;
            }
        }
        break;
    }
    return idx;
}

size_t
wcwidth_decode_cluster(const char *utf8, size_t lo, size_t hi, uint32_t *cps, size_t cap)
{
    size_t pos = lo;
    size_t count = 0;

    while (pos < hi && count < cap) {
        uint32_t cp;
        size_t consumed = wcwidth_utf8_decode_single(utf8 + pos, hi - pos, &cp);
        cps[count++] = cp;
        pos += consumed;
    }
    return count;
}
