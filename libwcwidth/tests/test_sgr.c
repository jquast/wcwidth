#include "test_common.h"
#include "wcwidth/sgr.h"
#include <stdlib.h>
#include <string.h>

/*
 * Parse a full SGR escape sequence and apply it to a fresh default state.
 */
static wcwidth_sgr_state_t
make_state(const char *sgr_esc)
{
    wcwidth_sgr_state_t s = WCWIDTH_SGR_STATE_DEFAULT;
    const char *start = strchr(sgr_esc, '[');
    const char *end = strchr(sgr_esc, 'm');

    if (start != NULL && end != NULL && end > start) {
        wcwidth_sgr_update(&s, start + 1, (size_t) (end - start - 1));
    }
    return s;
}

TEST(update_basic)
{
    wcwidth_sgr_state_t s = make_state("\x1b[1;31m");

    ASSERT_TRUE(s.bold);
    ASSERT_EQ(31, s.fg[0]);
    ASSERT_TRUE(wcwidth_sgr_is_active(&s));

    wcwidth_sgr_update(&s, "0", 1); /* reset */
    ASSERT_FALSE(s.bold);
    ASSERT_FALSE(wcwidth_sgr_is_active(&s));
}

TEST(is_active_basic)
{
    wcwidth_sgr_state_t s = WCWIDTH_SGR_STATE_DEFAULT;

    ASSERT_FALSE(wcwidth_sgr_is_active(&s));
    s.bold = true;
    ASSERT_TRUE(wcwidth_sgr_is_active(&s));
}

TEST(to_escape_basic)
{
    char buf[64];
    wcwidth_sgr_state_t s;

    s = WCWIDTH_SGR_STATE_DEFAULT;
    s.bold = true;
    s.fg[0] = 38;
    s.fg[1] = 5;
    s.fg[2] = 208;
    s.fg_len = 3;
    wcwidth_sgr_to_escape(&s, buf, sizeof(buf));
    ASSERT_STREQ("\x1b[1;38;5;208m", buf);
}

TEST(propagate_basic)
{
    char line1[256] = "\x1b[31mhello";
    char line2[256] = "world\x1b[0m";
    char *lines[] = {line1, line2};
    size_t line_lens[] = {strlen(line1), strlen(line2)};

    ASSERT_EQ(0, wcwidth_sgr_propagate(lines, line_lens, NULL, 2));
    ASSERT_STREQ("\x1b[31mhello\x1b[0m", lines[0]);
    ASSERT_STREQ("\x1b[31mworld\x1b[0m", lines[1]);

    /* C-only: empty input */
    ASSERT_EQ(0, wcwidth_sgr_propagate(NULL, NULL, NULL, 0));
}

/*
 * Exercise every capacity across the small-buffer boundary with guard bytes
 * on both sides of the destination buffer; the result must be
 * NUL-terminated strictly inside the buffer at every capacity, never
 * touching either guard.
 */
TEST(to_escape_bounded)
{
    static const size_t capacities[] = {0, 1, 2, 3, 4, 8, 16, 32, 63, 64,
                                        65, 128, 256, 512};
    size_t i;
    wcwidth_sgr_state_t s = WCWIDTH_SGR_STATE_DEFAULT;

    /* Maximal state: every boolean attribute plus 24-bit fg and bg. */
    s.bold = s.dim = s.italic = s.underline = s.blink = s.rapid_blink = true;
    s.inverse = s.hidden = s.strikethrough = s.double_underline = true;
    s.fg[0] = 38;
    s.fg[1] = 2;
    s.fg[2] = 255;
    s.fg[3] = 255;
    s.fg[4] = 255;
    s.fg_len = 5;
    s.bg[0] = 48;
    s.bg[1] = 2;
    s.bg[2] = 255;
    s.bg[3] = 255;
    s.bg[4] = 255;
    s.bg_len = 5;

    for (i = 0; i < sizeof(capacities) / sizeof(capacities[0]); i++) {
        size_t cap = capacities[i];
        size_t total = cap + 16;
        char *buf = malloc(total);
        size_t j;
        size_t written;

        ASSERT_NOT_NULL(buf);

        /* Guard bytes on both sides of the destination region. */
        memset(buf, 0xAA, 8);
        memset(buf + 8, 0x55, cap);
        memset(buf + 8 + cap, 0xAA, 8);

        written = wcwidth_sgr_to_escape(&s, buf + 8, cap);

        for (j = 0; j < 8; j++) {
            if ((unsigned char) buf[j] != 0xAA) {
                FAIL("leading guard clobbered at capacity %zu, byte %zu", cap, j);
            }
            if ((unsigned char) buf[8 + cap + j] != 0xAA) {
                FAIL("trailing guard clobbered at capacity %zu, byte %zu", cap, j);
            }
        }

        if (cap > 0) {
            /* written excludes the NUL; the NUL itself, and everything the
             * function touched, must fit inside [0, cap). */
            if (written >= cap) {
                FAIL("reported length %zu >= capacity %zu", written, cap);
            }
            if (buf[8 + written] != '\0') {
                FAIL("not NUL-terminated within buffer at capacity %zu", cap);
            }
        }

        free(buf);
    }
}

int
main(void)
{
    RUN_TEST(update_basic);
    RUN_TEST(is_active_basic);
    RUN_TEST(to_escape_basic);
    RUN_TEST(to_escape_bounded);
    RUN_TEST(propagate_basic);
    return test_summary();
}
