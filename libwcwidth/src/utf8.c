/*
 * UTF-8 decoding.
 */
#include "wcwidth/utf8.h"

#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

size_t
wcwidth_utf8_decode_single(const char *s, size_t len, uint32_t *cp_out)
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

uint32_t *
wcwidth_decode_u32(const char *utf8, size_t n, uint32_t *stack, size_t stack_cap, size_t *count)
{
    uint32_t *heap = NULL;
    uint32_t *out = stack;
    size_t cap = stack_cap;
    size_t used = 0;
    size_t pos = 0;

    while (pos < n) {
        uint32_t ucs;
        size_t consumed = wcwidth_utf8_decode_single(utf8 + pos, n - pos, &ucs);

        if (consumed == 0) {
            break;
        }
        if (used >= cap) {
            size_t new_cap = cap ? cap * 2 : 256;
            uint32_t *nd;

            if (new_cap < used + 1) {
                new_cap = used + 1;
            }
            if (heap == NULL) {
                nd = (uint32_t *) malloc(new_cap * sizeof(uint32_t));
                if (nd == NULL) {
                    *count = 0;
                    return NULL;
                }
                memcpy(nd, stack, used * sizeof(uint32_t));
            }
            else {
                nd = (uint32_t *) realloc(heap, new_cap * sizeof(uint32_t));
                if (nd == NULL) {
                    free(heap);
                    *count = 0;
                    return NULL;
                }
            }
            heap = nd;
            out = nd;
            cap = new_cap;
        }
        out[used++] = ucs;
        pos += consumed;
    }

    *count = used;
    return (heap != NULL) ? heap : stack;
}

uint32_t *
wcwidth_decode_u32_heap(const char *utf8, size_t n, size_t *count)
{
    uint32_t stack[128];
    uint32_t *decoded = wcwidth_decode_u32(utf8, n, stack, 128, count);
    uint32_t *heap;

    if (decoded == NULL) {
        return NULL;
    }
    if (decoded == stack) {
        heap = (uint32_t *) malloc(*count * sizeof(uint32_t));
        if (heap == NULL) {
            return NULL;
        }
        memcpy(heap, decoded, *count * sizeof(uint32_t));
    }
    else {
        heap = decoded; /* already heap-allocated; transfer ownership */
    }
    return heap;
}

/*
 * Encode one codepoint to UTF-8, writing at most 4 bytes to *out*.  Returns
 * the number of bytes written (1-4).  Invalid codepoints (lone surrogates,
 * values above U+10FFFF) are encoded as U+FFFD.
 */
static size_t
encode_single(uint32_t ucs, char *out)
{
    if (ucs > 0x10FFFF || (ucs >= 0xD800 && ucs <= 0xDFFF)) {
        ucs = 0xFFFD;
    }
    if (ucs < 0x80) {
        out[0] = (char) ucs;
        return 1;
    }
    if (ucs < 0x800) {
        out[0] = (char) (0xC0 | (ucs >> 6));
        out[1] = (char) (0x80 | (ucs & 0x3F));
        return 2;
    }
    if (ucs < 0x10000) {
        out[0] = (char) (0xE0 | (ucs >> 12));
        out[1] = (char) (0x80 | ((ucs >> 6) & 0x3F));
        out[2] = (char) (0x80 | (ucs & 0x3F));
        return 3;
    }
    out[0] = (char) (0xF0 | (ucs >> 18));
    out[1] = (char) (0x80 | ((ucs >> 12) & 0x3F));
    out[2] = (char) (0x80 | ((ucs >> 6) & 0x3F));
    out[3] = (char) (0x80 | (ucs & 0x3F));
    return 4;
}

char *
wcwidth_encode_u32(const uint32_t *codepoints, size_t n, char *stack, size_t stack_cap,
                   size_t *out_len)
{
    char *heap = NULL;
    char *out = stack;
    size_t cap = stack_cap;
    size_t used = 0;
    size_t i;

    for (i = 0; i < n; i++) {
        char tmp[4];
        size_t enc_len = encode_single(codepoints[i], tmp);

        if (used + enc_len > cap) {
            size_t new_cap = cap ? cap * 2 : 256;
            char *nd;

            if (new_cap < used + enc_len) {
                new_cap = used + enc_len;
            }
            if (heap == NULL) {
                nd = (char *) malloc(new_cap);
                if (nd == NULL) {
                    *out_len = 0;
                    return NULL;
                }
                memcpy(nd, stack, used);
            }
            else {
                nd = (char *) realloc(heap, new_cap);
                if (nd == NULL) {
                    free(heap);
                    *out_len = 0;
                    return NULL;
                }
            }
            heap = nd;
            out = nd;
            cap = new_cap;
        }
        memcpy(out + used, tmp, enc_len);
        used += enc_len;
    }

    *out_len = used;
    return (heap != NULL) ? heap : stack;
}
