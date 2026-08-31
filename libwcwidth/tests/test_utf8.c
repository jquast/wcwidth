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

int
main(void)
{
    RUN_TEST(encode_roundtrip);
    return test_summary();
}
