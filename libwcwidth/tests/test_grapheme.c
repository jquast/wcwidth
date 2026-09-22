#include "test_common.h"
#include "wcwidth/grapheme.h"
#include <string.h>

/* e + combining acute = e\u0301 */
#define STR_E_ACUTE "e\xcc\x81"

/* CRLF */
#define STR_CRLF "\x0d\x0a"

/* Hangul LV: U+1100 U+1161 */
#define STR_HANGUL_LV "\xe1\x84\x80\xe1\x85\xa1"

/* Flag US: U+1F1FA U+1F1F8 */
#define STR_FLAG_US "\xf0\x9f\x87\xba\xf0\x9f\x87\xb8"

/* Family: U+1F468 U+200D U+1F469 U+200D U+1F467 */
#define STR_FAMILY                                                                                 \
    "\xf0\x9f\x91\xa8\xe2\x80\x8d\xf0\x9f\x91\xa9"                                                 \
    "\xe2\x80\x8d\xf0\x9f\x91\xa7"

/* Wave + skin tone: U+1F44B U+1F3FB */
#define STR_WAVE_SKIN "\xf0\x9f\x91\x8b\xf0\x9f\x8f\xbb"

/* Devanagari virama + KA: U+094D U+0915 (InCB=Linker, InCB=Consonant) */
#define STR_VIRAMA_KA "\xe0\xa5\x8d\xe0\xa4\x95"

/* Vedic sign + KA: U+1CF5 U+0915 */
#define STR_VEDIC_KA "\xe1\xb3\xb5\xe0\xa4\x95"

/* Balinese: U+1B05 U+1B44 U+1B33 */
#define STR_BALINESE "\xe1\xac\x85\xe1\xad\x84\xe1\xac\xb3"

/* Zanabazar Square: U+11A3A U+11A0B */
#define STR_ZANABAZAR "\xf0\x91\xa8\xba\xf0\x91\xa8\x8b"

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

TEST(iterator_basic)
{
    /* exercises wcwidth_grapheme_iter_new / next / free */
    ASSERT_EQ(3, count_clusters("abc"));
    ASSERT_EQ(2, count_clusters("c" STR_E_ACUTE));
    ASSERT_EQ(1, count_clusters(STR_CRLF));
    ASSERT_EQ(1, count_clusters(STR_HANGUL_LV));
    ASSERT_EQ(1, count_clusters(STR_FLAG_US));
    ASSERT_EQ(1, count_clusters(STR_FAMILY));
    ASSERT_EQ(1, count_clusters(STR_WAVE_SKIN));
}

TEST(iterator_null_handling)
{
    size_t clen;
    wcwidth_grapheme_iter_t *iter = wcwidth_grapheme_iter_new("", 0);

    ASSERT_NOT_NULL(iter);
    ASSERT_NULL(wcwidth_grapheme_next(iter, &clen));
    wcwidth_grapheme_iter_free(iter);
    wcwidth_grapheme_iter_free(NULL);
    ASSERT_NULL(wcwidth_grapheme_next(NULL, &clen));
}

TEST(boundary_before_basic)
{
    char text[] = "cafe" STR_E_ACUTE; /* 7 bytes: e+acute cluster at 4 */
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_before("abc", 3, 3));
    ASSERT_EQ((int64_t) 4, (int64_t) wcwidth_grapheme_boundary_before(text, 7, 7));
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before("", 0, 0));
}

TEST(indic_conjunct_unicode18)
{
    /* Unicode 18.0.0 (UAX #29 revision 48) relaxed GB9c to
     * \p{InCB=Linker} \p{InCB=Extend}* x \p{InCB=Consonant}: a linker joins the
     * following consonant even with no consonant before it.  Mirrors
     * tests/test_grapheme.py::test_indic_conjunct_graphemes. */
    ASSERT_EQ((int64_t) 1, (int64_t) count_clusters(STR_VIRAMA_KA));
    ASSERT_EQ((int64_t) 1, (int64_t) count_clusters(STR_VEDIC_KA));
    ASSERT_EQ((int64_t) 1, (int64_t) count_clusters(STR_BALINESE));
    ASSERT_EQ((int64_t) 1, (int64_t) count_clusters(STR_ZANABAZAR));

    /* surrounding text still breaks normally */
    ASSERT_EQ((int64_t) 5, (int64_t) count_clusters("ok" STR_VEDIC_KA "ok"));
    ASSERT_EQ((int64_t) 5, (int64_t) count_clusters("ok" STR_BALINESE "ok"));
    ASSERT_EQ((int64_t) 5, (int64_t) count_clusters("ok" STR_ZANABAZAR "ok"));
}

/* ARABIC NUMBER SIGN U+0600, GCB=Prepend */
#define STR_PREPEND "\xd8\x80"

TEST(boundary_after_basic)
{
    /* "abc": every cluster is one byte */
    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_grapheme_boundary_after("abc", 3, 0));
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_after("abc", 3, 1));
    /* past the end, and empty input */
    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_grapheme_boundary_after("abc", 3, 3));
    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_grapheme_boundary_after("abc", 3, 99));
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_after("", 0, 0));

    /* multi-codepoint clusters report their whole extent from any byte within */
    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_grapheme_boundary_after(STR_E_ACUTE, 3, 0));
    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_grapheme_boundary_after(STR_E_ACUTE, 3, 1));
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_after(STR_CRLF, 2, 0));
    ASSERT_EQ((int64_t) 8, (int64_t) wcwidth_grapheme_boundary_after(STR_FLAG_US, 8, 0));
    ASSERT_EQ((int64_t) 18, (int64_t) wcwidth_grapheme_boundary_after(STR_FAMILY, 18, 0));

    /* a cluster followed by more text ends where the next one starts */
    ASSERT_EQ((int64_t) 8, (int64_t) wcwidth_grapheme_boundary_after(STR_FLAG_US "ok", 10, 0));
    ASSERT_EQ((int64_t) 9, (int64_t) wcwidth_grapheme_boundary_after(STR_FLAG_US "ok", 10, 8));
}

TEST(boundary_prepend_gb9b)
{
    /* GB9b: Prepend attaches to what follows, so the clusters are "a"
     * and <U+0600 b>, and the second starts at the PREPEND itself. */
    const char *text = "a" STR_PREPEND "b";

    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_grapheme_boundary_before(text, 4, 4));
    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_grapheme_boundary_before(text, 4, 3));
    ASSERT_EQ((int64_t) 2, (int64_t) count_clusters(text));
    ASSERT_EQ((int64_t) 1, (int64_t) wcwidth_grapheme_boundary_after(text, 4, 0));
    ASSERT_EQ((int64_t) 4, (int64_t) wcwidth_grapheme_boundary_after(text, 4, 1));
}

TEST(iterator_u32)
{
    /* "éok": one two-codepoint cluster then two single ones */
    static const uint32_t cps[] = {0x65, 0x301, 0x6F, 0x6B};
    wcwidth_grapheme_iter_t *iter = wcwidth_grapheme_iter_new_u32(cps, 4);
    const uint32_t *g;
    size_t len = 0;

    ASSERT_NOT_NULL(iter);
    g = wcwidth_grapheme_next_u32(iter, &len);
    ASSERT_TRUE(g == cps); /* borrowed pointer */
    ASSERT_EQ((int64_t) 2, (int64_t) len);
    g = wcwidth_grapheme_next_u32(iter, &len);
    ASSERT_TRUE(g == cps + 2);
    ASSERT_EQ((int64_t) 1, (int64_t) len);
    g = wcwidth_grapheme_next_u32(iter, &len);
    ASSERT_TRUE(g == cps + 3);
    ASSERT_EQ((int64_t) 1, (int64_t) len);
    ASSERT_NULL(wcwidth_grapheme_next_u32(iter, &len));
    wcwidth_grapheme_iter_free(iter);

    /* empty and NULL inputs */
    iter = wcwidth_grapheme_iter_new_u32(cps, 0);
    ASSERT_NOT_NULL(iter);
    ASSERT_NULL(wcwidth_grapheme_next_u32(iter, &len));
    wcwidth_grapheme_iter_free(iter);

    iter = wcwidth_grapheme_iter_new_u32(NULL, 0);
    ASSERT_NOT_NULL(iter);
    ASSERT_NULL(wcwidth_grapheme_next_u32(iter, &len));
    wcwidth_grapheme_iter_free(iter);
}

TEST(boundary_u32)
{
    /* flag, then "ok": clusters are [0,2), [2,3), [3,4) in codepoints */
    static const uint32_t cps[] = {0x1F1FA, 0x1F1F8, 0x6F, 0x6B};

    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before_u32(cps, 4, 2));
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_before_u32(cps, 4, 3));
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_after_u32(cps, 4, 0));
    ASSERT_EQ((int64_t) 2, (int64_t) wcwidth_grapheme_boundary_after_u32(cps, 4, 1));
    ASSERT_EQ((int64_t) 3, (int64_t) wcwidth_grapheme_boundary_after_u32(cps, 4, 2));

    /* degenerate inputs */
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before_u32(cps, 4, 0));
    ASSERT_EQ((int64_t) 4, (int64_t) wcwidth_grapheme_boundary_after_u32(cps, 4, 99));
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_before_u32(NULL, 0, 1));
    ASSERT_EQ((int64_t) 0, (int64_t) wcwidth_grapheme_boundary_after_u32(NULL, 0, 0));
}

int
main(void)
{
    RUN_TEST(iterator_basic);
    RUN_TEST(iterator_null_handling);
    RUN_TEST(boundary_before_basic);
    RUN_TEST(boundary_after_basic);
    RUN_TEST(boundary_prepend_gb9b);
    RUN_TEST(iterator_u32);
    RUN_TEST(boundary_u32);
    RUN_TEST(indic_conjunct_unicode18);
    return test_summary();
}
