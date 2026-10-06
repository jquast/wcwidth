#include "test_common.h"
#include "wcwidth/utf8.h"
#include <stdlib.h>
#include <string.h>

TEST(encode_roundtrip)
{
    const uint32_t cps[] = {'h', 0x00E9, 0x4E2D, 0x1F600};
    char stack[32];
    size_t len;
    size_t count;
    char *out;
    uint32_t dec[8];
    const uint32_t *back;

    out = wcwidth_encode_u32(cps, 4, stack, sizeof(stack), &len);
    ASSERT_NOT_NULL(out);
    ASSERT_EQ((int64_t) 10, (int64_t) len); /* 1 + 2 + 3 + 4 bytes */
    ASSERT_TRUE(out == stack);

    back = wcwidth_decode_u32(out, len, dec, 8, &count);
    ASSERT_EQ((int64_t) 4, (int64_t) count);
    ASSERT_EQ(0, memcmp(cps, back, sizeof(cps)));

    /* Invalid codepoints (surrogate, out of range) encode as U+FFFD. */
    {
        const uint32_t bad[] = {0xD800, 0x110000};

        out = wcwidth_encode_u32(bad, 2, stack, sizeof(stack), &len);
        ASSERT_NOT_NULL(out);
        ASSERT_EQ((int64_t) 6, (int64_t) len);
        ASSERT_EQ(0, memcmp(out, "\xef\xbf\xbd\xef\xbf\xbd", 6));
        ASSERT_TRUE(out == stack);
    }

    /* Overflowing the stack buffer heap-allocates; caller must free. */
    {
        uint32_t many[128];
        char small_stack[16];
        size_t i;

        for (i = 0; i < 128; i++) {
            many[i] = 0x4E2D; /* 3 bytes each */
        }
        out = wcwidth_encode_u32(many, 128, small_stack, sizeof(small_stack), &len);
        ASSERT_NOT_NULL(out);
        ASSERT_EQ((int64_t) (128 * 3), (int64_t) len);
        ASSERT_TRUE(out != small_stack);
        free(out);
    }
}

TEST(decode_malformed)
{
    static const char *const bad[] = {
        "\xf8",     "\xff",         "\xe2\x82",     "\xe2\x28\xa1",
        "\xc0\xaf", "\xe0\x80\xaf", "\xed\xa0\x80", "\xf4\x90\x80\x80"};
    size_t i;
    uint32_t cp = 0;

    ASSERT_EQ(0, wcwidth_utf8_decode_single("", 0, &cp));
    for (i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
        size_t used = wcwidth_utf8_decode_single(bad[i], strlen(bad[i]), &cp);

        ASSERT_EQ(0xFFFD, cp);
        ASSERT_TRUE(used >= 1 && used <= strlen(bad[i]));
    }
}

TEST(decode_u32_heap_empty)
{
    size_t count = 1;
    uint32_t *out = wcwidth_decode_u32_heap("", 0, &count);

    ASSERT_NOT_NULL(out);
    ASSERT_EQ((int64_t) 0, (int64_t) count);
    ASSERT_EQ((int64_t) 0, (int64_t) out[0]);
    free(out);
}

TEST(decode_single_null_out)
{
    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_utf8_decode_single("\xe4\xb8\xad", 3, NULL));
    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_utf8_decode_single("abc", 3, NULL));
}

TEST(decode_u32_null_stack)
{
    uint32_t *out;
    size_t count = 0;

    out = wcwidth_decode_u32("a", 1, NULL, 8, &count);
    ASSERT_NOT_NULL(out);
    ASSERT_EQ((int64_t) 1, (int64_t) count);
    ASSERT_EQ((int64_t) 'a', (int64_t) out[0]);
    free(out);
}

TEST(encode_u32_empty_heap)
{
    const uint32_t cps[] = {0};
    char *out;
    size_t len = 1;

    out = wcwidth_encode_u32(cps, 0, NULL, 0, &len);
    ASSERT_NOT_NULL(out);
    ASSERT_EQ((int64_t) 0, (int64_t) len);
    ASSERT_EQ((int64_t) 0, (int64_t) out[0]);
    free(out);
}

TEST(encode_u32_null_stack)
{
    const uint32_t cps[] = {'a', 'b'};
    char *out;
    size_t len = 0;

    out = wcwidth_encode_u32(cps, 2, NULL, 8, &len);
    ASSERT_NOT_NULL(out);
    ASSERT_EQ((int64_t) 2, (int64_t) len);
    ASSERT_EQ(0, memcmp(out, "ab", 2));
    free(out);
}

TEST(decode_u32_stack_overflow)
{
    uint32_t stack[2];
    uint32_t *out;
    size_t count = 0;

    out = wcwidth_decode_u32("abcdef", 6, stack, 2, &count);
    ASSERT_NOT_NULL(out);
    ASSERT_TRUE(out != stack);
    ASSERT_EQ((int64_t) 6, (int64_t) count);
    ASSERT_EQ((int64_t) 'a', (int64_t) out[0]);
    ASSERT_EQ((int64_t) 'f', (int64_t) out[5]);
    free(out);
}

int
main(void)
{
    RUN_TEST(encode_roundtrip);
    RUN_TEST(decode_malformed);
    RUN_TEST(decode_u32_heap_empty);
    RUN_TEST(decode_single_null_out);
    RUN_TEST(decode_u32_null_stack);
    RUN_TEST(encode_u32_empty_heap);
    RUN_TEST(encode_u32_null_stack);
    RUN_TEST(decode_u32_stack_overflow);
    return test_summary();
}
