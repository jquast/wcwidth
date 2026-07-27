/*
 * String display width with inline grapheme cluster tracking.
 *
 * Port of wcwidth/_wcswidth.py wcswidth().
 */
#include "wcwidth/wcwidth.h"
#include "wcwidth/tables.h"
#include "wcwidth/generated_tables.h"
#include "wcwidth/wcwidth_config.h"

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

static bool
is_regional_indicator(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, WCWIDTH_TABLE_GRAPHEME_REGIONAL_INDICATOR,
                            WCWIDTH_TABLE_GRAPHEME_REGIONAL_INDICATOR_LEN)
           != 0;
}

static bool
is_extended_pictographic(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, WCWIDTH_TABLE_EXTENDED_PICTOGRAPHIC,
                            WCWIDTH_TABLE_EXTENDED_PICTOGRAPHIC_LEN)
           != 0;
}

static bool
is_emoji_zwj_set(uint32_t ucs)
{
    return is_extended_pictographic(ucs) || is_regional_indicator(ucs);
}

/*
 * Codepoint ranges from Unicode IndicSyllabicCategory property where
 * ISC=Virama or ISC=Invisible_Stacker.  Sorted ascending, non-overlapping.
 */

static const wcwidth_interval_t ISC_VIRAMA_TABLE[] = {
    {0x0094d, 0x0094d}, /* Devanagari Sign Virama */
    {0x009cd, 0x009cd}, /* Bengali Sign Virama */
    {0x00a4d, 0x00a4d}, /* Gurmukhi Sign Virama */
    {0x00acd, 0x00acd}, /* Gujarati Sign Virama */
    {0x00b4d, 0x00b4d}, /* Oriya Sign Virama */
    {0x00bcd, 0x00bcd}, /* Tamil Sign Virama */
    {0x00c4d, 0x00c4d}, /* Telugu Sign Virama */
    {0x00ccd, 0x00ccd}, /* Kannada Sign Virama */
    {0x00d4d, 0x00d4d}, /* Malayalam Sign Virama */
    {0x00dca, 0x00dca}, /* Sinhala Sign Al-lakuna */
    {0x01039, 0x01039}, /* Myanmar Sign Virama (Invisible_Stacker) */
    {0x017d2, 0x017d2}, /* Khmer Sign Coeng (Invisible_Stacker) */
    {0x01a60, 0x01a60}, /* Tai Tham Sign Sakot (Invisible_Stacker) */
    {0x01b44, 0x01b44}, /* Balinese Adeg Adeg */
    {0x01bab, 0x01bab}, /* Sundanese Sign Virama (Invisible_Stacker) */
    {0x0a806, 0x0a806}, /* Syloti Nagri Sign Hasanta */
    {0x0a8c4, 0x0a8c4}, /* Saurashtra Sign Virama */
    {0x0a9c0, 0x0a9c0}, /* Javanese Pangkon */
    {0x0aaf6, 0x0aaf6}, /* Meetei Mayek Virama (Invisible_Stacker) */
    {0x10a3f, 0x10a3f}, /* Kharoshthi Virama (Invisible_Stacker) */
    {0x11046, 0x11046}, /* Brahmi Virama */
    {0x110b9, 0x110b9}, /* Kaithi Sign Virama */
    {0x11133, 0x11133}, /* Chakma Virama (Invisible_Stacker) */
    {0x111c0, 0x111c0}, /* Sharada Sign Virama */
    {0x11235, 0x11235}, /* Khojki Sign Virama */
    {0x1134d, 0x1134d}, /* Grantha Sign Virama */
    {0x113d0, 0x113d0}, /* Tulu-tigalari Conjoiner (Invisible_Stacker) */
    {0x11442, 0x11442}, /* Newa Sign Virama */
    {0x114c2, 0x114c2}, /* Tirhuta Sign Virama */
    {0x115bf, 0x115bf}, /* Siddham Sign Virama */
    {0x1163f, 0x1163f}, /* Modi Sign Virama */
    {0x116b6, 0x116b6}, /* Takri Sign Virama */
    {0x11839, 0x11839}, /* Dogra Sign Virama */
    {0x1193e, 0x1193e}, /* Dives Akuru Virama (Invisible_Stacker) */
    {0x119e0, 0x119e0}, /* Nandinagari Sign Virama */
    {0x11a47, 0x11a47}, /* Zanabazar Square Subjoiner (Invisible_Stacker) */
    {0x11a99, 0x11a99}, /* Soyombo Subjoiner (Invisible_Stacker) */
    {0x11c3f, 0x11c3f}, /* Bhaiksuki Sign Virama */
    {0x11d45, 0x11d45}, /* Masaram Gondi Virama (Invisible_Stacker) */
    {0x11d97, 0x11d97}, /* Gunjala Gondi Virama (Invisible_Stacker) */
    {0x11f42, 0x11f42}, /* Kawi Conjoiner (Invisible_Stacker) */
};

static const size_t ISC_VIRAMA_TABLE_LEN = sizeof ISC_VIRAMA_TABLE / sizeof ISC_VIRAMA_TABLE[0];

static bool
is_virama(uint32_t ucs)
{
    return wcwidth_bisearch(ucs, ISC_VIRAMA_TABLE, ISC_VIRAMA_TABLE_LEN) != 0;
}

#define FITZPATRICK_MIN 0x1F3FB
#define FITZPATRICK_MAX 0x1F3FF

static bool
is_fitzpatrick(uint32_t ucs)
{
    return ucs >= FITZPATRICK_MIN && ucs <= FITZPATRICK_MAX;
}

int
wcswidth_u32(const uint32_t *cp, size_t n, int ambiguous_width)
{
    size_t idx;
    int total_width;
    int cluster_width;
    int last_measured_idx;
    uint32_t last_measured_ucs;
    int last_measured_w;
    bool prev_was_virama;

    /* Empty input */
    if (n == 0 || cp == NULL) {
        return 0;
    }

    /* Fast path: pure ASCII printable strings are always width == length */
    {
        size_t i;
        bool all_ascii = true;
        for (i = 0; i < n; i++) {
            if (cp[i] < 32 || cp[i] >= 0x7f) {
                all_ascii = false;
                break;
            }
        }
        if (all_ascii) {
            return (int) n;
        }
    }

    total_width = 0;
    cluster_width = 0;
    idx = 0;
    last_measured_idx = -2;
    last_measured_ucs = 0;
    last_measured_w = 0;
    prev_was_virama = false;

    while (idx < n) {
        uint32_t ucs = cp[idx];

        if (ucs == 0x200D) {
            if (prev_was_virama) {
                idx += 1;
            }
            else if (idx + 1 < n) {
                last_measured_w = 0;
                prev_was_virama = false;
                idx += 2;
            }
            else {
                prev_was_virama = false;
                idx += 1;
            }
            continue;
        }

        if (ucs == 0xFE0F && last_measured_idx >= 0) {
            if (wcwidth_bisearch(last_measured_ucs, WCWIDTH_TABLE_VS16, WCWIDTH_TABLE_VS16_LEN)) {
                cluster_width = 2;
            }
            last_measured_idx = -2;
            idx += 1;
            continue;
        }

        if (ucs == 0xFE0E && last_measured_idx >= 0) {
            if (wcwidth_bisearch(last_measured_ucs, WCWIDTH_TABLE_VS15, WCWIDTH_TABLE_VS15_LEN)
                && last_measured_w == 2) {
                total_width -= 1;
            }
            idx += 1;
            continue;
        }

        if (ucs > 0xFFFF) {
            if (is_regional_indicator(ucs)) {
                int ri_before = 0;
                size_t j = idx;
                while (j > 0) {
                    j--;
                    if (is_regional_indicator(cp[j])) {
                        ri_before++;
                    }
                    else {
                        break;
                    }
                }
                if (ri_before % 2 == 1) {
                    last_measured_ucs = ucs;
                    idx += 1;
                    continue;
                }
            }
            else if (is_fitzpatrick(ucs) && last_measured_ucs != 0
                     && is_emoji_zwj_set(last_measured_ucs)) {
                idx += 1;
                continue;
            }
        }

        {
            int w = wcwidth_u32(ucs, ambiguous_width);
            if (w < 0) {
                return -1;
            }
            if (w > 0) {
                if (prev_was_virama) {
                    cluster_width = 2;
                }
                else if (cluster_width) {
                    total_width += cluster_width;
                    cluster_width = w;
                }
                else {
                    cluster_width = w;
                }
                last_measured_idx = (int) idx;
                last_measured_ucs = ucs;
                last_measured_w = w;
                prev_was_virama = false;
            }
            else if (is_virama(ucs)) {
                prev_was_virama = true;
            }
            else if (last_measured_idx >= 0
                     && wcwidth_bisearch(ucs, WCWIDTH_TABLE_MC, WCWIDTH_TABLE_MC_LEN)) {
                cluster_width = 2;
                last_measured_idx = -2;
                prev_was_virama = false;
            }
            else {
                prev_was_virama = false;
            }
        }
        idx += 1;
    }

    if (cluster_width) {
        total_width += cluster_width;
    }
    return total_width;
}

/*
 * Decode one UTF-8 codepoint from *s*.  Sets *cp_out and returns the
 * number of bytes consumed (1-4).  Returns 0 on error or truncation;
 * in that case *cp_out is set to 0xFFFD and the return value is the
 * number of bytes to skip (1 for a bad leading byte, or the remaining
 * length for a truncated sequence).
 */
static size_t
utf8_decode_single(const char *s, size_t len, uint32_t *cp_out)
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

    /* ASCII */
    if (c < 0x80) {
        *cp_out = c;
        return 1;
    }

    /* Determine sequence length */
    if (c < 0xC0) {
        /* Continuation byte at start -- invalid */
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
        /* Invalid leading byte (0xF8-0xFF) */
        *cp_out = 0xFFFD;
        return 1;
    }

    if (expected > len) {
        *cp_out = 0xFFFD;
        return len; /* Truncated -- consume remaining */
    }

    for (i = 1; i < expected; i++) {
        unsigned char cc = (unsigned char) s[i];
        if ((cc & 0xC0) != 0x80) {
            /* Broken sequence */
            *cp_out = 0xFFFD;
            return i;
        }
        cp = (cp << 6) | (cc & 0x3F);
    }

    /* Reject overlong sequences */
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

    /* Reject surrogates and values above U+10FFFF */
    if (cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) {
        *cp_out = 0xFFFD;
        return expected;
    }

    *cp_out = cp;
    return expected;
}

int
wcswidth_u8(const char *utf8, size_t n, int ambiguous_width)
{
    uint32_t cp_buf[512];
    size_t cp_count = 0;
    size_t pos = 0;
    int result;

    if (utf8 == NULL) {
        return 0;
    }

    /* Determine byte length */
    if (n == (size_t) -1) {
        n = 0;
        while (utf8[n] != '\0') {
            n++;
        }
    }

    if (n == 0) {
        return 0;
    }

    /* Decode UTF-8 to codepoints, using stack buffer for short strings */
    while (pos < n) {
        uint32_t ucs;
        size_t consumed = utf8_decode_single(utf8 + pos, n - pos, &ucs);

        if (consumed == 0) {
            break; /* Should not happen with n > 0 */
        }

        /* Grow if necessary */
        if (cp_count < sizeof cp_buf / sizeof cp_buf[0]) {
            cp_buf[cp_count++] = ucs;
        }
        else {
            /* Stack buffer exhausted -- fall through to measurement with
             * what we have so far, then measure the rest in-place. */
            result = wcswidth_u32(cp_buf, cp_count, ambiguous_width);
            if (result < 0) {
                return -1;
            }
            /* Measure the remaining tail */
            {
                int tail = wcswidth_u8(utf8 + pos, n - pos, ambiguous_width);
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
