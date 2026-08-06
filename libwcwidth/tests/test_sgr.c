#include "test_common.h"
#include "wcwidth/sgr.h"
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

int
main(void)
{
    RUN_TEST(update_basic);
    RUN_TEST(is_active_basic);
    RUN_TEST(to_escape_basic);
    RUN_TEST(propagate_basic);
    return test_summary();
}
