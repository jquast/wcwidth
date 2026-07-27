/*
 * Terminal-aware string width measurement.
 *
 * Port of wcwidth/_wcswidth.py wcstwidth().
 *
 * Terminal override tables are not yet generated; this implementation
 * delegates to wcswidth_u32/wcswidth_u8 when term_program is NULL or
 * when no overrides are available.  When terminal override data becomes
 * available, this file will be extended to apply per-terminal corrections
 * for single-codepoint overrides (narrower, zeroer, narrow_wider,
 * narrow_zeroer), VS16/VS15 variation overrides, and grapheme cluster
 * overrides.
 */
#include "wcwidth/wcwidth.h"
#include "wcwidth/tables.h"
#include "wcwidth/generated_tables.h"

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/*
 * Decode one UTF-8 codepoint from *s*.  See wcswidth.c for full documentation.
 */
static size_t
_utf8_decode_single(const char *s, size_t len, uint32_t *cp_out)
{
    unsigned char c;
    uint32_t cp;
    size_t expected;
    size_t i;

    if (len == 0) {
        *cp_out = 0xFFFD;
        return 0;
    }

    c = (unsigned char) s[0];

    if (c < 0x80) {
        *cp_out = c;
        return 1;
    }

    if (c < 0xC0) {
        *cp_out = 0xFFFD;
        return 1;
    }
    if (c < 0xE0) {
        expected = 2;
        cp = c & 0x1F;
    }
    else if (c < 0xF0) {
        expected = 3;
        cp = c & 0x0F;
    }
    else if (c < 0xF8) {
        expected = 4;
        cp = c & 0x07;
    }
    else {
        *cp_out = 0xFFFD;
        return 1;
    }

    if (expected > len) {
        *cp_out = 0xFFFD;
        return len;
    }

    for (i = 1; i < expected; i++) {
        unsigned char cc = (unsigned char) s[i];
        if ((cc & 0xC0) != 0x80) {
            *cp_out = 0xFFFD;
            return i;
        }
        cp = (cp << 6) | (cc & 0x3F);
    }

    if (expected == 2 && cp < 0x80) {
        *cp_out = 0xFFFD;
        return expected;
    }
    if (expected == 3 && cp < 0x800) {
        *cp_out = 0xFFFD;
        return expected;
    }
    if (expected == 4 && cp < 0x10000) {
        *cp_out = 0xFFFD;
        return expected;
    }

    if (cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) {
        *cp_out = 0xFFFD;
        return expected;
    }

    *cp_out = cp;
    return expected;
}

int
wcstwidth_u32(const uint32_t *codepoints, size_t n, int ambiguous_width, const char *term_program)
{
    (void) term_program; /* TODO: apply terminal override tables */

    return wcswidth_u32(codepoints, n, ambiguous_width);
}

int
wcstwidth_u8(const char *utf8, size_t n, int ambiguous_width, const char *term_program)
{
    uint32_t cp_buf[512];
    size_t cp_count = 0;
    size_t pos = 0;
    int result;

    (void) term_program; /* TODO: apply terminal override tables */

    if (utf8 == NULL) {
        return 0;
    }

    if (n == (size_t) -1) {
        n = strlen(utf8);
    }

    if (n == 0) {
        return 0;
    }

    while (pos < n) {
        uint32_t ucs;
        size_t consumed = _utf8_decode_single(utf8 + pos, n - pos, &ucs);

        if (consumed == 0) {
            break;
        }

        if (cp_count < sizeof cp_buf / sizeof cp_buf[0]) {
            cp_buf[cp_count++] = ucs;
        }
        else {
            result = wcswidth_u32(cp_buf, cp_count, ambiguous_width);
            if (result < 0) {
                return -1;
            }
            {
                int tail = wcstwidth_u8(utf8 + pos, n - pos, ambiguous_width, term_program);
                if (tail < 0) {
                    return -1;
                }
                return result + tail;
            }
        }
        pos += consumed;
    }

    return wcswidth_u32(cp_buf, cp_count, ambiguous_width);
}
