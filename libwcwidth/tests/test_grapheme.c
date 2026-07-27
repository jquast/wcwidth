#include "test_common.h"
#include "wcwidth/grapheme.h"
#include <string.h>

#define STR_CRLF "\x0d\x0a"
#define STR_CR "\x0d"
#define STR_LF "\x0a"

/* e + combining acute = e\u0301 */
#define STR_E_ACUTE "e\xcc\x81"

/* Hangul LV: U+1100 U+1161 */
#define STR_HANGUL_LV "\xe1\x84\x80\xe1\x85\xa1"

/* Hangul LVT: U+AC00 U+11A8 */
#define STR_HANGUL_LVT "\xea\xb0\x80\xe1\x86\xa8"

/* Flag US: U+1F1FA U+1F1F8 */
#define STR_FLAG_US "\xf0\x9f\x87\xba\xf0\x9f\x87\xb8"

/* Flag AU: U+1F1E6 U+1F1FA */
#define STR_FLAG_AU "\xf0\x9f\x87\xa6\xf0\x9f\x87\xba"

/* Single RI (A): U+1F1E6 */
#define STR_RI_A "\xf0\x9f\x87\xa6"

/* Family: U+1F468 U+200D U+1F469 U+200D U+1F467 */
#define STR_FAMILY                                                                                 \
    "\xf0\x9f\x91\xa8\xe2\x80\x8d\xf0\x9f\x91\xa9"                                                 \
    "\xe2\x80\x8d\xf0\x9f\x91\xa7"

/* Wave + skin tone: U+1F44B U+1F3FB */
#define STR_WAVE_SKIN "\xf0\x9f\x91\x8b\xf0\x9f\x8f\xbb"

/* Prepend char: U+0600 Arabic Number Sign */
#define STR_PREPEND "\xd8\x80"

/* e + acute + grave: e\u0301\u0300 */
#define STR_MULTI_COMBINE "e\xcc\x81\xcc\x80"

/* C1 control: NEL (U+0085) */
#define STR_NEL "\xc2\x85"

static int
count_clusters(const char *text)
{
    size_t len = strlen(text);
    wcwidth_grapheme_iter_t *iter = wcwidth_grapheme_iter_new(text, len);
    int count = 0;
    size_t clen;

    if (iter == NULL) {
        return -1;
    }
    while (wcwidth_grapheme_next(iter, &clen) != NULL) {
        count++;
    }
    wcwidth_grapheme_iter_free(iter);
    return count;
}

/* Compare a single cluster against expected string */
static void
check_cluster(const char *cluster, size_t clen, const char *expected)
{
    size_t exp_len = strlen(expected);
    ASSERT_EQ((int64_t) exp_len, (int64_t) clen);
    ASSERT_TRUE(memcmp(cluster, expected, clen) == 0);
}

TEST(empty_string)
{
    size_t clen;
    wcwidth_grapheme_iter_t *iter = wcwidth_grapheme_iter_new("", 0);
    ASSERT_NOT_NULL(iter);
    ASSERT_NULL(wcwidth_grapheme_next(iter, &clen));
    ASSERT_NULL(wcwidth_grapheme_next(iter, &clen));
    wcwidth_grapheme_iter_free(iter);
}

TEST(ascii_abc)
{
    ASSERT_EQ(3, count_clusters("abc"));
}

TEST(ascii_single)
{
    ASSERT_EQ(1, count_clusters("a"));
}

TEST(combining_acute)
{
    wcwidth_grapheme_iter_t *iter;
    size_t clen;
    const char *clust;
    int count = 0;

    iter = wcwidth_grapheme_iter_new("c" STR_E_ACUTE, strlen("c" STR_E_ACUTE));
    ASSERT_NOT_NULL(iter);

    clust = wcwidth_grapheme_next(iter, &clen);
    ASSERT_NOT_NULL(clust);
    check_cluster(clust, clen, "c");
    count++;

    clust = wcwidth_grapheme_next(iter, &clen);
    ASSERT_NOT_NULL(clust);
    check_cluster(clust, clen, STR_E_ACUTE);
    count++;

    ASSERT_NULL(wcwidth_grapheme_next(iter, &clen));
    ASSERT_EQ(2, count);
    wcwidth_grapheme_iter_free(iter);
}

TEST(multi_combining)
{
    ASSERT_EQ(5, count_clusters("cafe" STR_MULTI_COMBINE));
}

TEST(crlf_single_cluster)
{
    ASSERT_EQ(1, count_clusters(STR_CRLF));
}

TEST(crlf_with_text)
{
    ASSERT_EQ(5, count_clusters("ok" STR_CRLF "ok"));
}

TEST(cr_alone)
{
    ASSERT_EQ(1, count_clusters(STR_CR));
}

TEST(cr_with_text)
{
    ASSERT_EQ(5, count_clusters("ok" STR_CR "ok"));
}

TEST(lf_alone)
{
    ASSERT_EQ(1, count_clusters(STR_LF));
}

TEST(lf_with_text)
{
    ASSERT_EQ(5, count_clusters("ok" STR_LF "ok"));
}

TEST(cr_cr)
{
    ASSERT_EQ(2, count_clusters(STR_CR STR_CR));
}

TEST(cr_cr_with_text)
{
    ASSERT_EQ(6, count_clusters("ok" STR_CR STR_CR "ok"));
}

TEST(hangul_lv)
{
    ASSERT_EQ(1, count_clusters(STR_HANGUL_LV));
}

TEST(hangul_lv_with_text)
{
    ASSERT_EQ(5, count_clusters("ok" STR_HANGUL_LV "ok"));
}

TEST(hangul_lvt)
{
    ASSERT_EQ(1, count_clusters(STR_HANGUL_LVT));
}

TEST(hangul_lvt_with_text)
{
    ASSERT_EQ(5, count_clusters("ok" STR_HANGUL_LVT "ok"));
}

TEST(flag_single)
{
    ASSERT_EQ(1, count_clusters(STR_FLAG_US));
}

TEST(flag_with_text)
{
    ASSERT_EQ(5, count_clusters("ok" STR_FLAG_US "ok"));
}

TEST(flag_and_solo_ri)
{
    ASSERT_EQ(2, count_clusters(STR_FLAG_US STR_RI_A));
}

TEST(flag_plus_solo_ri_with_text)
{
    ASSERT_EQ(6, count_clusters("ok" STR_FLAG_US STR_RI_A "ok"));
}

TEST(two_flags)
{
    ASSERT_EQ(2, count_clusters(STR_FLAG_US STR_FLAG_AU));
}

TEST(two_flags_with_text)
{
    ASSERT_EQ(6, count_clusters("ok" STR_FLAG_US STR_FLAG_AU "ok"));
}

TEST(family)
{
    ASSERT_EQ(1, count_clusters(STR_FAMILY));
}

TEST(family_with_text)
{
    ASSERT_EQ(5, count_clusters("ok" STR_FAMILY "ok"));
}

TEST(wave_skin_tone)
{
    ASSERT_EQ(1, count_clusters(STR_WAVE_SKIN));
}

TEST(wave_skin_with_text)
{
    ASSERT_EQ(5, count_clusters("ok" STR_WAVE_SKIN "ok"));
}

TEST(iterator_cluster_lengths)
{
    wcwidth_grapheme_iter_t *iter;
    size_t clen;
    const char *clust;

    iter = wcwidth_grapheme_iter_new("abc", 3);
    ASSERT_NOT_NULL(iter);

    clust = wcwidth_grapheme_next(iter, &clen);
    ASSERT_NOT_NULL(clust);
    ASSERT_EQ(1, (int64_t) clen);
    ASSERT_EQ('a', clust[0]);

    clust = wcwidth_grapheme_next(iter, &clen);
    ASSERT_NOT_NULL(clust);
    ASSERT_EQ(1, (int64_t) clen);
    ASSERT_EQ('b', clust[0]);

    clust = wcwidth_grapheme_next(iter, &clen);
    ASSERT_NOT_NULL(clust);
    ASSERT_EQ(1, (int64_t) clen);
    ASSERT_EQ('c', clust[0]);

    ASSERT_NULL(wcwidth_grapheme_next(iter, &clen));
    wcwidth_grapheme_iter_free(iter);
}

TEST(iterator_null_input)
{
    size_t clen;
    wcwidth_grapheme_iter_t *iter = wcwidth_grapheme_iter_new("", 0);
    ASSERT_NOT_NULL(iter);
    ASSERT_NULL(wcwidth_grapheme_next(iter, &clen));
    wcwidth_grapheme_iter_free(iter);
}

TEST(iterator_free_null)
{
    wcwidth_grapheme_iter_free(NULL);
}

TEST(iterator_next_null_iter)
{
    size_t clen;
    ASSERT_NULL(wcwidth_grapheme_next(NULL, &clen));
}

TEST(boundary_before_abc)
{
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_before("abc", 3, 3));
    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_grapheme_boundary_before("abc", 3, 2));
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before("abc", 3, 1));
}

TEST(boundary_before_crlf)
{
    char text[] = "a" STR_CRLF "b";
    /* a(0) CR(1) LF(2) b(3) */
    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_grapheme_boundary_before(text, 4, 3));
}

TEST(boundary_before_combining)
{
    char text[] = "cafe" STR_E_ACUTE;
    size_t len = strlen(text);
    /* "cafee\u0301" (7 bytes): e\u0301 cluster starts at byte 4 */
    ASSERT_EQ((int64_t) 4, (int64_t) wcwidth_grapheme_boundary_before(text, len, len));
    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_grapheme_boundary_before(text, len, 4));
}

TEST(boundary_before_multi_combine)
{
    char text[] = "a" STR_MULTI_COMBINE "b";
    size_t len = strlen(text);
    /* "ae\u0301\u0300b" (7 bytes): e+marks cluster starts at byte 1 */
    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_grapheme_boundary_before(text, len, 6));
}

TEST(boundary_before_prepend)
{
    char text[] = STR_PREPEND "a";
    /* prepend(0-1) a(2) -- GB9b: Prepend x → no break */
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before(text, 3, 3));
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before(text, 3, 2));
}

TEST(boundary_before_prepend_control)
{
    char text[] = STR_PREPEND "\n";
    /* control breaks (GB4), so \n is at offset 2 */
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_before(text, 3, 3));
}

TEST(boundary_before_nel)
{
    char text[] = "X" STR_NEL "\xcc\x81";
    /* X(0) NEL(1-2) combining(3-4): NEL is CONTROL, breaks before combining */
    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_grapheme_boundary_before(text, 5, 5));
}

TEST(boundary_before_pos_zero)
{
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before("abc", 3, 0));
}

TEST(boundary_before_pos_beyond_len)
{
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_before("abc", 3, 100));
}

TEST(boundary_before_empty)
{
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before("", 0, 0));
}

TEST(boundary_before_wave_skin)
{
    char text[] = "Hi " STR_WAVE_SKIN "!";
    /* H(0) i(1) sp(2) wave(3-6) skin(7-10) !(11) */
    ASSERT_EQ((int64_t) 11, (int64_t) wcwidth_grapheme_boundary_before(text, 12, 12));
    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_grapheme_boundary_before(text, 12, 11));
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_before(text, 12, 3));
}

TEST(boundary_before_flag)
{
    char text[] = "a" STR_FLAG_US "b";
    /* a(0) flag(1-8) b(9) */
    ASSERT_EQ((int64_t) 9, (int64_t) wcwidth_grapheme_boundary_before(text, 10, 10));
    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_grapheme_boundary_before(text, 10, 9));
}

TEST(boundary_before_three_ri)
{
    char text[] = STR_FLAG_US STR_RI_A;
    /* flag(0-7) solo_ri(8-11) */
    ASSERT_EQ((int64_t) 8, (int64_t) wcwidth_grapheme_boundary_before(text, 12, 12));
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before(text, 12, 8));
}

TEST(boundary_before_family)
{
    char text[] = "a" STR_FAMILY "b";
    /* a(0) family(1-...) b */
    size_t family_len = strlen(STR_FAMILY);
    size_t len = 1 + family_len + 1;
    ASSERT_EQ((int64_t) (1 + family_len),
              (int64_t) wcwidth_grapheme_boundary_before(text, len, len));
    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_grapheme_boundary_before(text, len, 1 + family_len));
}

int
main(void)
{
    RUN_TEST(empty_string);
    RUN_TEST(ascii_abc);
    RUN_TEST(ascii_single);

    RUN_TEST(combining_acute);
    RUN_TEST(multi_combining);

    RUN_TEST(crlf_single_cluster);
    RUN_TEST(crlf_with_text);
    RUN_TEST(cr_alone);
    RUN_TEST(cr_with_text);
    RUN_TEST(lf_alone);
    RUN_TEST(lf_with_text);
    RUN_TEST(cr_cr);
    RUN_TEST(cr_cr_with_text);

    RUN_TEST(hangul_lv);
    RUN_TEST(hangul_lv_with_text);
    RUN_TEST(hangul_lvt);
    RUN_TEST(hangul_lvt_with_text);

    RUN_TEST(flag_single);
    RUN_TEST(flag_with_text);
    RUN_TEST(flag_and_solo_ri);
    RUN_TEST(flag_plus_solo_ri_with_text);
    RUN_TEST(two_flags);
    RUN_TEST(two_flags_with_text);

    RUN_TEST(family);
    RUN_TEST(family_with_text);

    RUN_TEST(wave_skin_tone);
    RUN_TEST(wave_skin_with_text);

    RUN_TEST(iterator_cluster_lengths);
    RUN_TEST(iterator_null_input);
    RUN_TEST(iterator_free_null);
    RUN_TEST(iterator_next_null_iter);

    RUN_TEST(boundary_before_abc);
    RUN_TEST(boundary_before_crlf);
    RUN_TEST(boundary_before_combining);
    RUN_TEST(boundary_before_multi_combine);
    RUN_TEST(boundary_before_prepend);
    RUN_TEST(boundary_before_prepend_control);
    RUN_TEST(boundary_before_nel);
    RUN_TEST(boundary_before_pos_zero);
    RUN_TEST(boundary_before_pos_beyond_len);
    RUN_TEST(boundary_before_empty);

    RUN_TEST(boundary_before_wave_skin);
    RUN_TEST(boundary_before_flag);
    RUN_TEST(boundary_before_three_ri);
    RUN_TEST(boundary_before_family);

    return test_summary();
}
