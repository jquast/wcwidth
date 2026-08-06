#include "test_common.h"
#include "wcwidth/hyperlink.h"
#include <string.h>

TEST(parse_open_basic)
{
    wcwidth_hyperlink_params_t p;
    const char *seq = "\x1b]8;id=a;http://example.com\x1b\\";
    size_t seq_len = strlen(seq);

    ASSERT_TRUE(wcwidth_hyperlink_parse_open(seq, seq_len, &p));
    ASSERT_EQ((size_t) 4, p.params_len);
    ASSERT_TRUE(memcmp(p.params, "id=a", 4) == 0);
    ASSERT_EQ((size_t) 18, p.url_len);
    ASSERT_TRUE(memcmp(p.url, "http://example.com", 18) == 0);
    ASSERT_EQ('\x1b', p.terminator);

    ASSERT_FALSE(wcwidth_hyperlink_parse_open("\x1b[31m", 5, &p));
    ASSERT_FALSE(wcwidth_hyperlink_parse_open("", 0, &p));
}

TEST(roundtrip_basic)
{
    /* parse_open + make_open + make_close reproduce the original sequence */
    wcwidth_hyperlink_params_t params;
    const char *open_seq = "\x1b]8;;http://example.com\x07";
    const char *inner = "Hello";
    const char *expected = "\x1b]8;;http://example.com\x07Hello\x1b]8;;\x07";
    char rebuild[128];
    char *p = rebuild;
    size_t n;

    ASSERT_TRUE(wcwidth_hyperlink_parse_open(open_seq, strlen(open_seq), &params));
    n = wcwidth_hyperlink_make_open(&params, p, sizeof(rebuild) - (size_t) (p - rebuild));
    p += n;
    memcpy(p, inner, strlen(inner));
    p += strlen(inner);
    n = wcwidth_hyperlink_make_close(params.terminator, p,
                                     sizeof(rebuild) - (size_t) (p - rebuild));
    p += n;

    ASSERT_EQ(strlen(expected), (size_t) (p - rebuild));
    ASSERT_TRUE(memcmp(rebuild, expected, (size_t) (p - rebuild)) == 0);
}

TEST(find_close_basic)
{
    const char *text = "\x1b]8;;http://example.com\x07Hello\x1b]8;;\x07";
    size_t close_start, close_end;

    wcwidth_hyperlink_find_close(text, strlen(text), 0, &close_start, &close_end);
    ASSERT_EQ((size_t) 29, close_start);
    ASSERT_EQ((size_t) 35, close_end);

    wcwidth_hyperlink_find_close("Hello world", 11, 0, &close_start, &close_end);
    ASSERT_EQ((size_t) -1, close_start);
    ASSERT_EQ((size_t) -1, close_end);
}

TEST(next_id_basic)
{
    char id[8];
    int i;

    wcwidth_hyperlink_next_id(id);
    for (i = 0; i < 8; i++) {
        ASSERT_TRUE((id[i] >= '0' && id[i] <= '9') || (id[i] >= 'a' && id[i] <= 'f'));
    }
}

int
main(void)
{
    RUN_TEST(parse_open_basic);
    RUN_TEST(roundtrip_basic);
    RUN_TEST(find_close_basic);
    RUN_TEST(next_id_basic);
    return test_summary();
}
