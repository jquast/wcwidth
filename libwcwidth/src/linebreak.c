/*
 * UAX #14 line breaking.  These rules mirror wcwidth.linebreak; LineBreakTest.txt is the parity
 * reference.
 */
#include "wcwidth/bitset_tables.h"
#include "wcwidth/linebreak.h"
#include "wcwidth/tables.h"

#include <stdbool.h>
#include <stdlib.h>

#define LB(name) WCWIDTH_LB_##name

typedef struct
{
    bool allowed;
    bool mandatory;
} lb_break_t;

typedef struct
{
    size_t start;
    size_t end;
    unsigned cls;
    bool ends_zwj;
} lb_cluster_t;

#define NO_BREAK ((lb_break_t) {false, false})
#define BREAK ((lb_break_t) {true, false})
#define MANDATORY_BREAK ((lb_break_t) {true, true})

static bool
in_table(uint32_t ucs, const wcwidth_interval_t *table, size_t table_len)
{
    return wcwidth_bisearch(ucs, table, table_len) != 0;
}

static bool
is_east_asian(uint32_t ucs)
{
    return wcwidth_bitset_get(ucs, WCWIDTH_LINEBREAK_EAST_ASIAN_MIN,
                              WCWIDTH_LINEBREAK_EAST_ASIAN_MAX, WCWIDTH_LINEBREAK_EAST_ASIAN_INDEX,
                              WCWIDTH_LINEBREAK_EAST_ASIAN_POOL);
}

static bool
is_pi_qu(uint32_t ucs, unsigned cls)
{
    return cls == LB(QU) && in_table(ucs, WCWIDTH_LINEBREAK_PI_QU, WCWIDTH_LINEBREAK_PI_QU_LEN);
}

static bool
is_pf_qu(uint32_t ucs, unsigned cls)
{
    return cls == LB(QU) && in_table(ucs, WCWIDTH_LINEBREAK_PF_QU, WCWIDTH_LINEBREAK_PF_QU_LEN);
}

static bool
is_ext_pict_cn(uint32_t ucs)
{
    return in_table(ucs, WCWIDTH_LINEBREAK_EXT_PICT_CN, WCWIDTH_LINEBREAK_EXT_PICT_CN_LEN);
}

unsigned
wcwidth_linebreak_class(uint32_t ucs)
{
    if (ucs < WCWIDTH_LINEBREAK_ASCII_LEN)
        return WCWIDTH_LINEBREAK_ASCII[ucs];
    return wcwidth_linebreak_class_get(ucs);
}

static unsigned
resolved_class(uint32_t ucs)
{
    unsigned cls;

    if (ucs < WCWIDTH_LINEBREAK_ASCII_LEN)
        return WCWIDTH_LINEBREAK_ASCII_RESOLVED[ucs];
    cls = wcwidth_linebreak_class_get(ucs);
    switch (cls) {
        case WCWIDTH_LB_AI:
        case WCWIDTH_LB_SG:
        case WCWIDTH_LB_XX:
            return WCWIDTH_LB_AL;
        case WCWIDTH_LB_CJ:
            return WCWIDTH_LB_NS;
        case WCWIDTH_LB_SA:
            return wcwidth_bitset_get(ucs, WCWIDTH_LINEBREAK_SA_CM_MIN, WCWIDTH_LINEBREAK_SA_CM_MAX,
                                      WCWIDTH_LINEBREAK_SA_CM_INDEX, WCWIDTH_LINEBREAK_SA_CM_POOL)
                       ? WCWIDTH_LB_CM
                       : WCWIDTH_LB_AL;
        default:
            return cls;
    }
}

static bool
is_no_base(unsigned cls)
{
    return cls == LB(BK) || cls == LB(CR) || cls == LB(LF) || cls == LB(NL) || cls == LB(SP)
           || cls == LB(ZW);
}

static int
nu_before(size_t idx, const lb_cluster_t *cl)
{
    while (cl[idx].cls == LB(SY) || cl[idx].cls == LB(IS)) {
        if (idx == 0)
            return -1;
        idx--;
    }
    return cl[idx].cls == LB(NU) ? (int) idx : -1;
}

static bool
is_dotted(size_t index, unsigned cls, const uint32_t *cps, const lb_cluster_t *cl)
{
    return cls == LB(AK) || cls == LB(AS) || cps[cl[index].start] == 0x25CC;
}

static lb_break_t
break_at(size_t idx, const uint32_t *cps, const lb_cluster_t *cl, size_t count, size_t ri_run)
{
    unsigned before = cl[idx].cls;
    unsigned after = cl[idx + 1].cls;
    uint32_t before_cp = cps[cl[idx].start];
    uint32_t after_cp = cps[cl[idx + 1].start];
    size_t look;
    unsigned prior;
    unsigned next;

    if (before == LB(BK))
        return MANDATORY_BREAK;
    if (before == LB(CR))
        return after == LB(LF) ? NO_BREAK : MANDATORY_BREAK;
    if (before == LB(LF) || before == LB(NL))
        return MANDATORY_BREAK;

    if (after == LB(BK) || after == LB(CR) || after == LB(LF) || after == LB(NL))
        return NO_BREAK;
    if (after == LB(SP) || after == LB(ZW))
        return NO_BREAK;

    if (before == LB(AL) && after == LB(AL))
        return NO_BREAK; /* LB28, the dominant pair in running text */

    look = idx;
    while (cl[look].cls == LB(SP)) {
        if (look == 0) {
            look = SIZE_MAX;
            break;
        }
        look--;
    }
    if (look != SIZE_MAX && cl[look].cls == LB(ZW))
        return BREAK;

    if (before == LB(SP) && after == LB(AL)) {
        if (look != SIZE_MAX) {
            if (cl[look].cls == LB(OP))
                return NO_BREAK; /* LB14 */
            if (is_pi_qu(cps[cl[look].start], cl[look].cls)) {
                if (look == 0)
                    return NO_BREAK; /* LB15a */
                prior = cl[look - 1].cls;
                if (prior == LB(BK) || prior == LB(CR) || prior == LB(LF) || prior == LB(NL)
                    || prior == LB(OP) || prior == LB(QU) || prior == LB(GL) || prior == LB(SP)
                    || prior == LB(ZW))
                    return NO_BREAK; /* LB15a */
            }
        }
        return BREAK; /* LB18 */
    }

    if (before == LB(ID) && after == LB(ID) && !cl[idx].ends_zwj)
        return BREAK; /* LB31, with LB8a excluded */

    if (cl[idx].ends_zwj)
        return NO_BREAK;

    if (before == LB(WJ) || after == LB(WJ))
        return NO_BREAK;

    if (before == LB(GL))
        return NO_BREAK;

    if (after == LB(GL) && before != LB(SP) && before != LB(HY) && before != LB(HH))
        return NO_BREAK;

    if (after == LB(CL) || after == LB(CP) || after == LB(EX) || after == LB(SY))
        return NO_BREAK;

    if (look != SIZE_MAX && cl[look].cls == LB(OP))
        return NO_BREAK;

    if (look != SIZE_MAX && is_pi_qu(cps[cl[look].start], cl[look].cls)) {
        if (look == 0)
            return NO_BREAK;
        prior = cl[look - 1].cls;
        if (prior == LB(BK) || prior == LB(CR) || prior == LB(LF) || prior == LB(NL)
            || prior == LB(OP) || prior == LB(QU) || prior == LB(GL) || prior == LB(SP)
            || prior == LB(ZW))
            return NO_BREAK;
    }

    if (is_pf_qu(after_cp, after)) {
        if (idx + 2 >= count)
            return NO_BREAK;
        next = cl[idx + 2].cls;
        if (next == LB(SP) || next == LB(GL) || next == LB(WJ) || next == LB(CL) || next == LB(QU)
            || next == LB(CP) || next == LB(EX) || next == LB(IS) || next == LB(SY)
            || next == LB(BK) || next == LB(CR) || next == LB(LF) || next == LB(NL)
            || next == LB(ZW))
            return NO_BREAK;
    }

    if (before == LB(SP) && after == LB(IS) && idx + 2 < count && cl[idx + 2].cls == LB(NU))
        return BREAK;

    if (after == LB(IS))
        return NO_BREAK;

    if (after == LB(NS)) {
        if (look != SIZE_MAX && (cl[look].cls == LB(CL) || cl[look].cls == LB(CP)))
            return NO_BREAK;
    }

    if (after == LB(B2)) {
        if (look != SIZE_MAX && cl[look].cls == LB(B2))
            return NO_BREAK;
    }

    if (before == LB(SP))
        return BREAK;

    if (after == LB(QU) && !is_pi_qu(after_cp, after))
        return NO_BREAK;
    if (before == LB(QU) && !is_pf_qu(before_cp, before))
        return NO_BREAK;

    if (after == LB(QU) && !is_east_asian(before_cp))
        return NO_BREAK;
    if (after == LB(QU)) {
        if (idx + 2 >= count || !is_east_asian(cps[cl[idx + 2].start]))
            return NO_BREAK;
    }
    if (before == LB(QU) && !is_east_asian(after_cp))
        return NO_BREAK;
    if (before == LB(QU)) {
        if (idx == 0 || !is_east_asian(cps[cl[idx - 1].start]))
            return NO_BREAK;
    }

    if (after == LB(CB) || before == LB(CB))
        return BREAK;

    if ((before == LB(HY) || before == LB(HH)) && (after == LB(AL) || after == LB(HL))) {
        if (idx == 0)
            return NO_BREAK;
        prior = cl[idx - 1].cls;
        if (prior == LB(BK) || prior == LB(CR) || prior == LB(LF) || prior == LB(NL)
            || prior == LB(SP) || prior == LB(ZW) || prior == LB(CB) || prior == LB(GL))
            return NO_BREAK;
    }

    if (after == LB(BA) || after == LB(HH) || after == LB(HY) || after == LB(NS))
        return NO_BREAK;
    if (before == LB(BB))
        return NO_BREAK;

    if ((before == LB(HY) || before == LB(HH)) && after != LB(HL) && idx > 0
        && cl[idx - 1].cls == LB(HL))
        return NO_BREAK;

    if (before == LB(SY) && after == LB(HL))
        return NO_BREAK;

    if (after == LB(IN))
        return NO_BREAK;

    if (((before == LB(AL) || before == LB(HL)) && after == LB(NU))
        || (before == LB(NU) && (after == LB(AL) || after == LB(HL))))
        return NO_BREAK;

    if ((before == LB(PR) && (after == LB(ID) || after == LB(EB) || after == LB(EM)))
        || ((before == LB(ID) || before == LB(EB) || before == LB(EM)) && after == LB(PO)))
        return NO_BREAK;

    if (((before == LB(PR) || before == LB(PO)) && (after == LB(AL) || after == LB(HL)))
        || ((before == LB(AL) || before == LB(HL)) && (after == LB(PR) || after == LB(PO))))
        return NO_BREAK;

    if (after == LB(PO) || after == LB(PR)) {
        if (nu_before(idx, cl) >= 0)
            return NO_BREAK;
        if ((before == LB(CL) || before == LB(CP)) && idx > 0 && nu_before(idx - 1, cl) >= 0)
            return NO_BREAK;
    }
    if ((before == LB(PO) || before == LB(PR)) && after == LB(OP)) {
        next = (idx + 2 < count) ? cl[idx + 2].cls : 0xFF;
        if (next == LB(NU) || (next == LB(IS) && idx + 3 < count && cl[idx + 3].cls == LB(NU)))
            return NO_BREAK;
    }
    if ((before == LB(PO) || before == LB(PR)) && after == LB(NU))
        return NO_BREAK;
    if ((before == LB(HY) || before == LB(IS)) && after == LB(NU))
        return NO_BREAK;
    if (after == LB(NU) && nu_before(idx, cl) >= 0)
        return NO_BREAK;

    if ((before == LB(JL)
         && (after == LB(JL) || after == LB(JV) || after == LB(H2) || after == LB(H3)))
        || ((before == LB(JV) || before == LB(H2)) && (after == LB(JV) || after == LB(JT)))
        || ((before == LB(JT) || before == LB(H3)) && after == LB(JT)))
        return NO_BREAK;

    if (((before == LB(JL) || before == LB(JV) || before == LB(JT) || before == LB(H2)
          || before == LB(H3))
         && after == LB(PO))
        || (before == LB(PR)
            && (after == LB(JL) || after == LB(JV) || after == LB(JT) || after == LB(H2)
                || after == LB(H3))))
        return NO_BREAK;

    if ((before == LB(AL) || before == LB(HL)) && (after == LB(AL) || after == LB(HL)))
        return NO_BREAK;

    if (before == LB(AP) && is_dotted(idx + 1, after, cps, cl))
        return NO_BREAK;
    if (is_dotted(idx, before, cps, cl) && (after == LB(VF) || after == LB(VI)))
        return NO_BREAK;
    if (before == LB(VI) && idx > 0 && is_dotted(idx - 1, cl[idx - 1].cls, cps, cl)
        && is_dotted(idx + 1, after, cps, cl))
        return NO_BREAK;
    if (is_dotted(idx, before, cps, cl) && is_dotted(idx + 1, after, cps, cl) && idx + 2 < count
        && cl[idx + 2].cls == LB(VF))
        return NO_BREAK;

    if (before == LB(IS) && (after == LB(AL) || after == LB(HL)))
        return NO_BREAK;

    if ((before == LB(AL) || before == LB(HL) || before == LB(NU)) && after == LB(OP)
        && !is_east_asian(after_cp))
        return NO_BREAK;
    if (before == LB(CP) && (after == LB(AL) || after == LB(HL) || after == LB(NU))
        && !is_east_asian(before_cp))
        return NO_BREAK;

    if (before == LB(RI) && after == LB(RI))
        return (ri_run % 2 == 0) ? BREAK : NO_BREAK;

    if (after == LB(EM) && (before == LB(EB) || is_ext_pict_cn(before_cp)))
        return NO_BREAK;

    return BREAK;
}

size_t
wcwidth_linebreak_breaks_u32(const uint32_t *cps, size_t n, size_t *breaks, uint8_t *mandatory,
                             size_t cap, bool hyphens)
{
    lb_cluster_t *cl;
    size_t count = 0;
    size_t i;
    size_t written = 0;
    size_t idx;
    size_t ri_run = 0;

    if (n == 0)
        return 0;
    if (n > SIZE_MAX / sizeof(*cl))
        return (size_t) -1;

    cl = malloc(n * sizeof(*cl));
    if (cl == NULL)
        goto fail;

    i = 0;
    while (i < n) {
        unsigned cls = resolved_class(cps[i]);
        bool ends_zwj = (cls == LB(ZWJ));

        cl[count].start = i;
        cl[count].cls = (cls == LB(CM) || cls == LB(ZWJ)) ? LB(AL) : cls;
        i++;
        if (!is_no_base(cl[count].cls)) {
            while (i < n) {
                cls = resolved_class(cps[i]);
                if (cls != LB(CM) && cls != LB(ZWJ))
                    break;
                ends_zwj = (cls == LB(ZWJ));
                i++;
            }
        }
        cl[count].end = i;
        cl[count].ends_zwj = ends_zwj;
        count++;
    }

    for (idx = 0; idx + 1 < count; idx++) {
        lb_break_t result;

        ri_run = (cl[idx].cls == LB(RI)) ? ri_run + 1 : 0;
        result = break_at(idx, cps, cl, count, ri_run);
        if (!result.allowed)
            continue;
        if (!hyphens && !result.mandatory && (cl[idx].cls == LB(HY) || cl[idx].cls == LB(HH)))
            continue;
        if (written >= cap)
            goto fail;
        breaks[written] = cl[idx].end;
        if (mandatory != NULL)
            mandatory[written] = result.mandatory ? 1u : 0u;
        written++;
    }
    if (written >= cap)
        goto fail;
    breaks[written] = n;
    if (mandatory != NULL)
        mandatory[written] = 0;
    written++;

    free(cl);
    return written;

fail:
    free(cl);
    return (size_t) -1;
}
