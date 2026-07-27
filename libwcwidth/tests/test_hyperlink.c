#include "test_common.h"
#include "wcwidth/hyperlink.h"
#include <string.h>
#include <stdio.h>

TEST(parse_open_bel_empty_params)
{
    wcwidth_hyperlink_params_t p;
    const char *seq = "\x1b]8;;http://example.com\x07";
    size_t seq_len = strlen(seq);

    ASSERT_TRUE(wcwidth_hyperlink_parse_open(seq, seq_len, &p));
    ASSERT_EQ((size_t) 0, p.params_len);
    ASSERT_EQ((size_t) 18, p.url_len);
    ASSERT_TRUE(memcmp(p.url, "http://example.com", 18) == 0);
    ASSERT_EQ('\x07', p.terminator);
}

TEST(parse_open_st_with_id)
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
}

TEST(parse_open_url_with_semicolons)
{
    wcwidth_hyperlink_params_t p;
    const char *seq = "\x1b]8;id=1;http://example.com?a=1;b=2\x07";
    size_t seq_len = strlen(seq);

    ASSERT_TRUE(wcwidth_hyperlink_parse_open(seq, seq_len, &p));
    ASSERT_EQ((size_t) 4, p.params_len);
    ASSERT_TRUE(memcmp(p.params, "id=1", 4) == 0);
    ASSERT_EQ((size_t) 26, p.url_len);
    ASSERT_TRUE(memcmp(p.url, "http://example.com?a=1;b=2", 26) == 0);
    ASSERT_EQ('\x07', p.terminator);
}

TEST(parse_open_invalid_not_osc8)
{
    wcwidth_hyperlink_params_t p;
    ASSERT_FALSE(wcwidth_hyperlink_parse_open("not an escape", 13, &p));
}

TEST(parse_open_invalid_sgr)
{
    wcwidth_hyperlink_params_t p;
    const char *seq = "\x1b[31m";
    ASSERT_FALSE(wcwidth_hyperlink_parse_open(seq, strlen(seq), &p));
}

TEST(parse_open_invalid_empty)
{
    wcwidth_hyperlink_params_t p;
    ASSERT_FALSE(wcwidth_hyperlink_parse_open("", 0, &p));
}

TEST(parse_open_invalid_missing_semi)
{
    wcwidth_hyperlink_params_t p;
    const char *seq = "\x1b]8http://example.com\x07";
    ASSERT_FALSE(wcwidth_hyperlink_parse_open(seq, strlen(seq), &p));
}

TEST(parse_open_invalid_no_terminator)
{
    wcwidth_hyperlink_params_t p;
    const char *seq = "\x1b]8;id=a;http://example.com";
    ASSERT_FALSE(wcwidth_hyperlink_parse_open(seq, strlen(seq), &p));
}

TEST(parse_open_invalid_too_short)
{
    wcwidth_hyperlink_params_t p;
    ASSERT_FALSE(wcwidth_hyperlink_parse_open("\x1b]8", 3, &p));
}

TEST(make_open_bel)
{
    wcwidth_hyperlink_params_t params;
    char buf[64];
    size_t n;

    params.url = "http://example.com";
    params.url_len = 18;
    params.params = "id=a";
    params.params_len = 4;
    params.terminator = '\x07';

    n = wcwidth_hyperlink_make_open(&params, buf, sizeof(buf));
    ASSERT_EQ((size_t) 28, n);
    ASSERT_TRUE(memcmp(buf, "\x1b]8;id=a;http://example.com\x07", 28) == 0);
}

TEST(make_open_st)
{
    wcwidth_hyperlink_params_t params;
    char buf[64];
    size_t n;

    params.url = "http://example.com";
    params.url_len = 18;
    params.params = "";
    params.params_len = 0;
    params.terminator = '\x1b';

    n = wcwidth_hyperlink_make_open(&params, buf, sizeof(buf));
    ASSERT_EQ((size_t) 25, n);
    ASSERT_TRUE(memcmp(buf, "\x1b]8;;http://example.com\x1b\\", 25) == 0);
}

TEST(make_close_bel)
{
    char buf[16];
    size_t n = wcwidth_hyperlink_make_close('\x07', buf, sizeof(buf));
    ASSERT_EQ((size_t) 6, n);
    ASSERT_TRUE(memcmp(buf, "\x1b]8;;\x07", 6) == 0);
}

TEST(make_close_st)
{
    char buf[16];
    size_t n = wcwidth_hyperlink_make_close('\x1b', buf, sizeof(buf));
    ASSERT_EQ((size_t) 7, n);
    ASSERT_TRUE(memcmp(buf, "\x1b]8;;\x1b\\", 7) == 0);
}

TEST(find_close_bel)
{
    const char *text = "\x1b]8;;http://example.com\x07Hello\x1b]8;;\x07";
    size_t close_start, close_end;

    wcwidth_hyperlink_find_close(text, strlen(text), 0, &close_start, &close_end);
    ASSERT_EQ((size_t) 29, close_start);
    ASSERT_EQ((size_t) 35, close_end);
}

TEST(find_close_st)
{
    const char *text = "\x1b]8;id=1;https://example.com\x1b\\world\x1b]8;;\x1b\\";
    size_t close_start, close_end;

    wcwidth_hyperlink_find_close(text, strlen(text), 0, &close_start, &close_end);
    ASSERT_EQ((size_t) 35, close_start);
    ASSERT_EQ((size_t) 42, close_end);
}

TEST(find_close_not_found)
{
    size_t close_start = 0, close_end = 0;
    wcwidth_hyperlink_find_close("no escape here", 14, 0, &close_start, &close_end);
    ASSERT_EQ((size_t) -1, close_start);
    ASSERT_EQ((size_t) -1, close_end);
}

TEST(find_close_not_found_plain_text)
{
    size_t close_start = 0, close_end = 0;
    wcwidth_hyperlink_find_close("Hello world", 11, 0, &close_start, &close_end);
    ASSERT_EQ((size_t) -1, close_start);
    ASSERT_EQ((size_t) -1, close_end);
}

TEST(find_close_respects_search_start)
{
    const char *text = "\x1b]8;;\x07\x1b]8;;\x07";
    size_t close_start, close_end;

    wcwidth_hyperlink_find_close(text, strlen(text), 1, &close_start, &close_end);
    ASSERT_EQ((size_t) 6, close_start);
    ASSERT_EQ((size_t) 12, close_end);
}

TEST(roundtrip_bel)
{
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

TEST(roundtrip_st)
{
    wcwidth_hyperlink_params_t params;
    const char *open_seq = "\x1b]8;id=a;http://example.com\x1b\\";
    const char *inner = "world";
    const char *expected = "\x1b]8;id=a;http://example.com\x1b\\world\x1b]8;;\x1b\\";
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

TEST(next_id_produces_eight_hex_chars)
{
    char id[8];
    int i;

    wcwidth_hyperlink_next_id(id);

    for (i = 0; i < 8; i++) {
        ASSERT_TRUE((id[i] >= '0' && id[i] <= '9') || (id[i] >= 'a' && id[i] <= 'f'));
    }
}

TEST(next_id_produces_different_values)
{
    char id1[8], id2[8];

    wcwidth_hyperlink_next_id(id1);
    wcwidth_hyperlink_next_id(id2);

    ASSERT_TRUE(memcmp(id1, id2, 8) != 0);
}

int
main(void)
{
    RUN_TEST(parse_open_bel_empty_params);
    RUN_TEST(parse_open_st_with_id);
    RUN_TEST(parse_open_url_with_semicolons);
    RUN_TEST(parse_open_invalid_not_osc8);
    RUN_TEST(parse_open_invalid_sgr);
    RUN_TEST(parse_open_invalid_empty);
    RUN_TEST(parse_open_invalid_missing_semi);
    RUN_TEST(parse_open_invalid_no_terminator);
    RUN_TEST(parse_open_invalid_too_short);

    RUN_TEST(make_open_bel);
    RUN_TEST(make_open_st);

    RUN_TEST(make_close_bel);
    RUN_TEST(make_close_st);

    RUN_TEST(find_close_bel);
    RUN_TEST(find_close_st);
    RUN_TEST(find_close_not_found);
    RUN_TEST(find_close_not_found_plain_text);
    RUN_TEST(find_close_respects_search_start);

    RUN_TEST(roundtrip_bel);
    RUN_TEST(roundtrip_st);

    RUN_TEST(next_id_produces_eight_hex_chars);
    RUN_TEST(next_id_produces_different_values);

    return test_summary();
}
