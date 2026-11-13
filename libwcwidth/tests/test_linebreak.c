#include "test_common.h"
#include "wcwidth/linebreak.h"
#include "wcwidth/tables.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define UNICODE_MAX 0x10FFFF

static void
check_breaks_with(const uint32_t *cps, size_t n, const size_t *expected, size_t expected_len,
                  bool hyphens)
{
    size_t breaks[64];
    uint8_t mandatory[64];
    size_t got = wcwidth_linebreak_breaks_u32(cps, n, breaks, mandatory, 64, hyphens);
    size_t i;

    ASSERT_EQ((int64_t) expected_len, (int64_t) got);
    for (i = 0; i < expected_len; i++)
        ASSERT_EQ((int64_t) expected[i], (int64_t) breaks[i]);
}

static void
check_breaks(const uint32_t *cps, size_t n, const size_t *expected, size_t expected_len)
{
    check_breaks_with(cps, n, expected, expected_len, true);
}

TEST(linebreak_classes)
{
    ASSERT_EQ((int64_t) WCWIDTH_LB_ZW, (int64_t) wcwidth_linebreak_class(0x200B));
    ASSERT_EQ((int64_t) WCWIDTH_LB_WJ, (int64_t) wcwidth_linebreak_class(0x2060));
    ASSERT_EQ((int64_t) WCWIDTH_LB_WJ, (int64_t) wcwidth_linebreak_class(0xFEFF));
    ASSERT_EQ((int64_t) WCWIDTH_LB_GL, (int64_t) wcwidth_linebreak_class(0x00A0));
    ASSERT_EQ((int64_t) WCWIDTH_LB_GL, (int64_t) wcwidth_linebreak_class(0x202F));
    ASSERT_EQ((int64_t) WCWIDTH_LB_GL, (int64_t) wcwidth_linebreak_class(0x2007));
    ASSERT_EQ((int64_t) WCWIDTH_LB_HH, (int64_t) wcwidth_linebreak_class(0x00AD));
    ASSERT_EQ((int64_t) WCWIDTH_LB_BA, (int64_t) wcwidth_linebreak_class(0x1680));
    ASSERT_EQ((int64_t) WCWIDTH_LB_BA, (int64_t) wcwidth_linebreak_class(0x3000));
    ASSERT_EQ((int64_t) WCWIDTH_LB_BA, (int64_t) wcwidth_linebreak_class(0x2000));
    ASSERT_EQ((int64_t) WCWIDTH_LB_HY, (int64_t) wcwidth_linebreak_class(0x002D));
    ASSERT_EQ((int64_t) WCWIDTH_LB_SP, (int64_t) wcwidth_linebreak_class(0x0020));
}

TEST(linebreak_zwsp)
{
    const uint32_t cps[] = {'a', 0x200B, 'b'};
    const size_t expected[] = {2, 3};
    check_breaks(cps, 3, expected, 2);
}

TEST(linebreak_no_break)
{
    const uint32_t nbsp[] = {'a', 0x00A0, 'b'};
    const uint32_t nnbsp[] = {'a', 0x202F, 'b'};
    const uint32_t figure[] = {'a', 0x2007, 'b'};
    const uint32_t wj[] = {'a', 0x2060, 'b'};
    const uint32_t zwnbsp[] = {'a', 0xFEFF, 'b'};
    const size_t expected[] = {3};

    check_breaks(nbsp, 3, expected, 1);
    check_breaks(nnbsp, 3, expected, 1);
    check_breaks(figure, 3, expected, 1);
    check_breaks(wj, 3, expected, 1);
    check_breaks(zwnbsp, 3, expected, 1);
}

TEST(linebreak_breaking_spaces)
{
    const uint32_t ideographic[] = {'a', 0x3000, 'b'};
    const uint32_t ogham[] = {'a', 0x1680, 'b'};
    const uint32_t en_quad[] = {'a', 0x2000, 'b'};
    const uint32_t hair[] = {'a', 0x200A, 'b'};
    const size_t expected[] = {2, 3};

    check_breaks(ideographic, 3, expected, 2);
    check_breaks(ogham, 3, expected, 2);
    check_breaks(en_quad, 3, expected, 2);
    check_breaks(hair, 3, expected, 2);
}

TEST(linebreak_hyphens)
{
    const uint32_t hyphen_minus[] = {'a', '-', 'b'};
    const uint32_t soft_hyphen[] = {'a', 0x00AD, 'b'};
    const uint32_t hyphen[] = {'a', 0x2010, 'b'};
    const size_t expected[] = {2, 3};

    check_breaks(hyphen_minus, 3, expected, 2);
    check_breaks(soft_hyphen, 3, expected, 2);
    check_breaks(hyphen, 3, expected, 2);
}

TEST(linebreak_without_hyphens)
{
    const uint32_t hyphen_minus[] = {'a', '-', 'b'};
    const uint32_t soft_hyphen[] = {'a', 0x00AD, 'b'};
    const uint32_t hyphen[] = {'a', 0x2010, 'b'};
    const size_t expected[] = {3};

    check_breaks_with(hyphen_minus, 3, expected, 1, false);
    check_breaks_with(soft_hyphen, 3, expected, 1, false);
    check_breaks_with(hyphen, 3, expected, 1, false);
}

TEST(linebreak_mandatory)
{
    const uint32_t lf[] = {'a', '\n', 'b'};
    const uint32_t crlf[] = {'a', '\r', '\n', 'b'};
    size_t breaks[8];
    uint8_t mandatory[8];
    size_t got;

    got = wcwidth_linebreak_breaks_u32(lf, 3, breaks, mandatory, 8, true);
    ASSERT_EQ((int64_t) 2, (int64_t) got);
    ASSERT_EQ((int64_t) 2, (int64_t) breaks[0]);
    ASSERT_EQ((int64_t) 1, (int64_t) mandatory[0]);
    ASSERT_EQ((int64_t) 3, (int64_t) breaks[1]);
    ASSERT_EQ((int64_t) 0, (int64_t) mandatory[1]);

    got = wcwidth_linebreak_breaks_u32(crlf, 4, breaks, mandatory, 8, true);
    ASSERT_EQ((int64_t) 2, (int64_t) got);
    ASSERT_EQ((int64_t) 3, (int64_t) breaks[0]);
    ASSERT_EQ((int64_t) 1, (int64_t) mandatory[0]);
    ASSERT_EQ((int64_t) 4, (int64_t) breaks[1]);
}

TEST(linebreak_regional_indicators)
{
    uint32_t cps[8];
    const size_t expected[] = {2, 4, 6, 8};
    size_t i;

    for (i = 0; i < 8; i += 2) {
        cps[i] = 0x1F1FA;
        cps[i + 1] = 0x1F1F8;
    }
    check_breaks(cps, 8, expected, 4);
}

TEST(linebreak_empty)
{
    size_t breaks[1];
    uint8_t mandatory[1];
    ASSERT_EQ((int64_t) 0,
              (int64_t) wcwidth_linebreak_breaks_u32(NULL, 0, breaks, mandatory, 1, true));
}

TEST(linebreak_class_boundaries)
{
    ASSERT_EQ((int64_t) WCWIDTH_LB_CM, (int64_t) wcwidth_linebreak_class(0x0000));
    ASSERT_EQ((int64_t) WCWIDTH_LB_BA, (int64_t) wcwidth_linebreak_class(0x0009));
    ASSERT_EQ((int64_t) WCWIDTH_LB_LF, (int64_t) wcwidth_linebreak_class(0x000A));
    ASSERT_EQ((int64_t) WCWIDTH_LB_CR, (int64_t) wcwidth_linebreak_class(0x000D));
    ASSERT_EQ((int64_t) WCWIDTH_LB_SP, (int64_t) wcwidth_linebreak_class(0x0020));
    ASSERT_EQ((int64_t) WCWIDTH_LB_QU, (int64_t) wcwidth_linebreak_class(0x0022));
    ASSERT_EQ((int64_t) WCWIDTH_LB_OP, (int64_t) wcwidth_linebreak_class(0x0028));
    ASSERT_EQ((int64_t) WCWIDTH_LB_CP, (int64_t) wcwidth_linebreak_class(0x0029));
    ASSERT_EQ((int64_t) WCWIDTH_LB_HY, (int64_t) wcwidth_linebreak_class(0x002D));
    ASSERT_EQ((int64_t) WCWIDTH_LB_SY, (int64_t) wcwidth_linebreak_class(0x002F));
    ASSERT_EQ((int64_t) WCWIDTH_LB_NU, (int64_t) wcwidth_linebreak_class(0x0030));
    ASSERT_EQ((int64_t) WCWIDTH_LB_EX, (int64_t) wcwidth_linebreak_class(0x003F));
    ASSERT_EQ((int64_t) WCWIDTH_LB_AL, (int64_t) wcwidth_linebreak_class(0x0041));
    ASSERT_EQ((int64_t) WCWIDTH_LB_CM, (int64_t) wcwidth_linebreak_class(0x007F));
    ASSERT_EQ((int64_t) WCWIDTH_LB_CM, (int64_t) wcwidth_linebreak_class(0x0080));
    ASSERT_EQ((int64_t) WCWIDTH_LB_GL, (int64_t) wcwidth_linebreak_class(0x00A0));
    ASSERT_EQ((int64_t) WCWIDTH_LB_AL, (int64_t) wcwidth_linebreak_class(0x10FF));
    ASSERT_EQ((int64_t) WCWIDTH_LB_JL, (int64_t) wcwidth_linebreak_class(0x1100));
    ASSERT_EQ((int64_t) WCWIDTH_LB_XX, (int64_t) wcwidth_linebreak_class(UNICODE_MAX));
}

TEST(linebreak_class_out_of_range)
{
    ASSERT_EQ((int64_t) WCWIDTH_LB_XX, (int64_t) wcwidth_linebreak_class(UNICODE_MAX + 1));
    ASSERT_EQ((int64_t) WCWIDTH_LB_XX, (int64_t) wcwidth_linebreak_class(UINT32_MAX));
}

TEST(linebreak_small_capacity)
{
    const uint32_t cps[] = {'a', ' ', 'b'};
    size_t breaks[2];
    uint8_t mandatory[2];

    ASSERT_EQ((int64_t) -1,
              (int64_t) wcwidth_linebreak_breaks_u32(cps, 3, breaks, mandatory, 0, true));
    ASSERT_EQ((int64_t) -1,
              (int64_t) wcwidth_linebreak_breaks_u32(cps, 3, breaks, mandatory, 1, true));
}

TEST(linebreak_initial_quote_contexts)
{
    static const uint32_t spaced[] = {0x0B, 0x0D, 0x0A, 0x85, 0x20, 0x200B};
    static const uint32_t unspaced[] = {'(', '"', 0xA0, 'a'};
    const size_t two[] = {1, 3};
    const size_t one[] = {3};
    const uint32_t pi_qu = 0x00AB;
    const uint32_t at_start[] = {0x00AB, 'a'};
    const size_t end[] = {2};
    uint32_t cps[3];
    size_t i;

    for (i = 0; i < sizeof(spaced) / sizeof(spaced[0]); i++) {
        cps[0] = spaced[i];
        cps[1] = pi_qu;
        cps[2] = 'a';
        check_breaks(cps, 3, two, 2);
    }
    for (i = 0; i < sizeof(unspaced) / sizeof(unspaced[0]); i++) {
        cps[0] = unspaced[i];
        cps[1] = pi_qu;
        cps[2] = 'a';
        check_breaks(cps, 3, one, 1);
    }
    check_breaks(at_start, 2, end, 1);

    {
        static const uint32_t quote_spaced[] = {0x0B, 0x0D, 0x0A, 0x85, 0x20, 0x200B};
        static const uint32_t quote_unspaced[] = {'(', '"', 0xA0};
        const size_t quote_two[] = {1, 4};
        const size_t quote_one[] = {4};
        const uint32_t quote_al[] = {'a', 0x00AB, 0x20, 'a'};
        const size_t quote_al_breaks[] = {3, 4};
        uint32_t spaced_cps[4];

        for (i = 0; i < sizeof(quote_spaced) / sizeof(quote_spaced[0]); i++) {
            spaced_cps[0] = quote_spaced[i];
            spaced_cps[1] = pi_qu;
            spaced_cps[2] = ' ';
            spaced_cps[3] = 'a';
            check_breaks(spaced_cps, 4, quote_two, 2);
        }
        for (i = 0; i < sizeof(quote_unspaced) / sizeof(quote_unspaced[0]); i++) {
            spaced_cps[0] = quote_unspaced[i];
            spaced_cps[1] = pi_qu;
            spaced_cps[2] = ' ';
            spaced_cps[3] = 'a';
            check_breaks(spaced_cps, 4, quote_one, 1);
        }
        check_breaks(quote_al, 4, quote_al_breaks, 2);
    }
}

TEST(linebreak_final_quote_contexts)
{
    static const uint32_t suffix[] = {0x20, 0xA0, 0x2060, '}',  '"',  ')',  '!',
                                      ',',  '/',  0x0B,   0x0D, 0x0A, 0x85, 0x200B};
    const size_t expected[] = {3};
    const uint32_t pf_qu = 0x00BB;
    const uint32_t alone[] = {'a', 0x00BB};
    const size_t end[] = {2};
    uint32_t cps[3];
    size_t i;

    for (i = 0; i < sizeof(suffix) / sizeof(suffix[0]); i++) {
        cps[0] = 'a';
        cps[1] = pf_qu;
        cps[2] = suffix[i];
        check_breaks(cps, 3, expected, 1);
    }
    check_breaks(alone, 2, end, 1);
}

TEST(linebreak_east_asian_quotes)
{
    const uint32_t ea_qu[] = {0x3009, '"'};
    const uint32_t qu_ea[] = {'"', 0x3009};
    const uint32_t ea_qu_ea[] = {0x3009, '"', 0x3009};
    const uint32_t ea_qu_al[] = {0x3009, '"', 'a'};
    const uint32_t qu_ea_ea[] = {'"', 0x3009, 0x3009};
    const uint32_t qu_ea_al[] = {'"', 0x3009, 'a'};
    const size_t end[] = {2};
    const size_t all[] = {3};
    const size_t ea_al[] = {2, 3};

    check_breaks(ea_qu, 2, end, 1);
    check_breaks(qu_ea, 2, end, 1);
    check_breaks(ea_qu_ea, 3, all, 1);
    check_breaks(ea_qu_al, 3, all, 1);
    check_breaks(qu_ea_ea, 3, all, 1);
    check_breaks(qu_ea_al, 3, ea_al, 2);
}

TEST(linebreak_hyphen_contexts)
{
    static const uint32_t before[] = {0x0B, 0x0D, 0x0A, 0x85, 0x20, 0x200B, 0xFFFC};
    const size_t two[] = {1, 3};
    const size_t one[] = {3};
    uint32_t cps[3];
    size_t i;

    for (i = 0; i < sizeof(before) / sizeof(before[0]); i++) {
        cps[0] = before[i];
        cps[1] = '-';
        cps[2] = 'a';
        check_breaks(cps, 3, two, 2);
    }
    cps[0] = 0xA0;
    cps[1] = '-';
    cps[2] = 'a';
    check_breaks(cps, 3, one, 1);
}

TEST(linebreak_numeric_contexts)
{
    const uint32_t po_op_nu[] = {'%', '(', '0'};
    const uint32_t po_op_is_nu[] = {'%', '(', ',', '0'};
    const uint32_t po_op_is_al[] = {'%', '(', ',', 'a'};
    const uint32_t po_op_is[] = {'%', '(', ','};
    const uint32_t nu_is_cl_po[] = {'0', ',', '}', '%'};
    const uint32_t nu_is_cp_po[] = {'0', ',', ')', '%'};
    const uint32_t al_is_cl_po[] = {'a', ',', '}', '%'};
    const size_t all3[] = {3};
    const size_t all4[] = {4};
    const size_t split3[] = {1, 3};
    const size_t split4[] = {1, 4};
    const size_t al_split4[] = {3, 4};

    check_breaks(po_op_nu, 3, all3, 1);
    check_breaks(po_op_is_nu, 4, all4, 1);
    check_breaks(po_op_is_al, 4, split4, 2);
    check_breaks(po_op_is, 3, split3, 2);
    check_breaks(nu_is_cl_po, 4, all4, 1);
    check_breaks(nu_is_cp_po, 4, all4, 1);
    check_breaks(al_is_cl_po, 4, al_split4, 2);
}

TEST(linebreak_dotted_circle)
{
    const uint32_t ap_dot[] = {0x11003, 0x25CC};
    const uint32_t dot_vf[] = {0x25CC, 0x1BF2};
    const uint32_t dot_vi[] = {0x25CC, 0x1B44};
    const uint32_t vi_dot_dot[] = {0x1B44, 0x25CC, 0x25CC};
    const uint32_t dot_dot_vf[] = {0x25CC, 0x25CC, 0x1BF2};
    const uint32_t dot_vi_dot[] = {0x25CC, 0x1B44, 0x25CC};
    const uint32_t dot_vi_al[] = {0x25CC, 0x1B44, 'a'};
    const uint32_t al_vi_dot[] = {'a', 0x1B44, 0x25CC};
    const size_t two[] = {2};
    const size_t all[] = {3};
    const size_t split[] = {1, 3};
    const size_t dot_all[] = {2, 3};
    const size_t al_split[] = {1, 2, 3};

    check_breaks(ap_dot, 2, two, 1);
    check_breaks(dot_vf, 2, two, 1);
    check_breaks(dot_vi, 2, two, 1);
    check_breaks(vi_dot_dot, 3, split, 2);
    check_breaks(dot_dot_vf, 3, all, 1);
    check_breaks(dot_vi_dot, 3, all, 1);
    check_breaks(dot_vi_al, 3, dot_all, 2);
    check_breaks(al_vi_dot, 3, al_split, 3);
}

TEST(linebreak_mandatory_optional)
{
    const uint32_t cps[] = {'a', ' ', 'b'};
    size_t breaks[4];
    size_t got = wcwidth_linebreak_breaks_u32(cps, 3, breaks, NULL, 4, true);

    ASSERT_EQ((int64_t) 2, (int64_t) got);
    ASSERT_EQ((int64_t) 2, (int64_t) breaks[0]);
    ASSERT_EQ((int64_t) 3, (int64_t) breaks[1]);
}

static FILE *
open_line_break_test(void)
{
#ifdef WCWIDTH_TEST_DIR
    char path[4096];
    FILE *configured;

    snprintf(path, sizeof(path), "%s/LineBreakTest.txt", WCWIDTH_TEST_DIR);
    configured = fopen(path, "r");
    if (configured != NULL)
        return configured;
#endif
    static const char *paths[] = {
        "tests/LineBreakTest.txt",
        "../tests/LineBreakTest.txt",
        "../../tests/LineBreakTest.txt",
        "../../../tests/LineBreakTest.txt",
        "../../../../tests/LineBreakTest.txt",
    };
    size_t i;

    for (i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
        FILE *test_file = fopen(paths[i], "r");
        if (test_file != NULL)
            return test_file;
    }
    return NULL;
}

TEST(linebreak_conformance)
{
    FILE *test_file = open_line_break_test();
    char buffer[4096];
    size_t line_number = 0;
    size_t failures = 0;
    size_t cases = 0;

    if (test_file == NULL) {
        fprintf(stderr, "LineBreakTest.txt is missing; run bin/update-tables.py\n");
        return;
    }

    while (fgets(buffer, sizeof(buffer), test_file) != NULL) {
        char *hash;
        char *token;
        uint32_t cps[512];
        size_t expected[512];
        size_t breaks[512];
        uint8_t mandatory[512];
        size_t ncps = 0;
        size_t nexpected = 0;
        size_t got;
        bool pending = false;
        size_t i;

        line_number++;
        if (strchr(buffer, '\n') == NULL) {
            int ch;
            while ((ch = fgetc(test_file)) != EOF && ch != '\n') {
            }
        }
        hash = strchr(buffer, '#');
        if (hash != NULL)
            *hash = '\0';

        token = strtok(buffer, " \t\r\n");
        while (token != NULL) {
            if (strcmp(token, "\xc3\xb7") == 0) {
                pending = true;
            }
            else if (strcmp(token, "\xc3\x97") == 0) {
                pending = false;
            }
            else {
                unsigned long cp = strtoul(token, NULL, 16);
                if (pending && nexpected < 512)
                    expected[nexpected++] = ncps;
                if (ncps < 512)
                    cps[ncps++] = (uint32_t) cp;
            }
            token = strtok(NULL, " \t\r\n");
        }
        if (ncps == 0)
            continue;
        if (pending && nexpected < 512)
            expected[nexpected++] = ncps;

        cases++;
        got = wcwidth_linebreak_breaks_u32(cps, ncps, breaks, mandatory, 512, true);
        if (got != nexpected) {
            if (failures < 10)
                fprintf(stderr, "line %zu: expected %zu breaks, got %zu\n", line_number, nexpected,
                        got);
            failures++;
            continue;
        }
        for (i = 0; i < got; i++) {
            if (breaks[i] != expected[i]) {
                if (failures < 10)
                    fprintf(stderr, "line %zu: break %zu expected %zu, got %zu\n", line_number, i,
                            expected[i], breaks[i]);
                failures++;
                break;
            }
        }
    }
    fclose(test_file);

    if (cases == 0)
        fprintf(stderr, "LineBreakTest.txt had no cases\n");
    ASSERT_EQ((int64_t) 0, (int64_t) failures);
}

int
main(void)
{
    RUN_TEST(linebreak_classes);
    RUN_TEST(linebreak_zwsp);
    RUN_TEST(linebreak_no_break);
    RUN_TEST(linebreak_breaking_spaces);
    RUN_TEST(linebreak_hyphens);
    RUN_TEST(linebreak_without_hyphens);
    RUN_TEST(linebreak_mandatory);
    RUN_TEST(linebreak_regional_indicators);
    RUN_TEST(linebreak_empty);
    RUN_TEST(linebreak_class_boundaries);
    RUN_TEST(linebreak_class_out_of_range);
    RUN_TEST(linebreak_small_capacity);
    RUN_TEST(linebreak_initial_quote_contexts);
    RUN_TEST(linebreak_final_quote_contexts);
    RUN_TEST(linebreak_east_asian_quotes);
    RUN_TEST(linebreak_hyphen_contexts);
    RUN_TEST(linebreak_numeric_contexts);
    RUN_TEST(linebreak_dotted_circle);
    RUN_TEST(linebreak_mandatory_optional);
    RUN_TEST(linebreak_conformance);
    return test_summary();
}
