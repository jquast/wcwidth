/*
 * CPython extension wrapping libwcwidth.
 *
 * Optional module: when this module cannot be imported, wcwidth/__init__.py
 * falls back to the Python implementation.
 *
 * A lone surrogate has no UTF-8 form, so the functions that encode to UTF-8
 * cannot accept one.  align(), strip_sequences() and propagate_sgr() hand such
 * input back to the Python implementation; clip() returns None, and its caller
 * in wcwidth/_clip.py falls through to the Python code below the offload.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* A free-threaded build needs Py_mod_gil, which Py_LIMITED_API below 3.13
 * drops. */
#if defined(Py_LIMITED_API) && defined(Py_GIL_DISABLED)
#  error "Py_LIMITED_API must not be set for a free-threaded build"
#endif

#include "wcwidth/wcwidth.h"
#include "wcwidth/width.h"
#include "wcwidth/align.h"
#include "wcwidth/clip.h"
#include "wcwidth/escape.h"
#include "wcwidth/sgr.h"
#include "wcwidth/grapheme.h"

/* Return the codepoints of text in a new PyMem_Malloc'd buffer. */
static uint32_t *
unicode_codepoints(PyObject *text, Py_ssize_t *count)
{
    Py_ssize_t len = PyUnicode_GetLength(text);
    Py_UCS4 *buf;

    if (len < 0) {
        return NULL;
    }
    buf = PyUnicode_AsUCS4Copy(text);
    if (buf == NULL) {
        return NULL;
    }
    *count = len;
    return (uint32_t *)buf;
}

/* Return obj's type name as UTF-8, and a reference to it in *name_out.  The
 * limited API does not expose tp_name, so read the type's __name__. */
static const char *
type_name_utf8(PyObject *obj, PyObject **name_out)
{
    PyObject *name = PyObject_GetAttrString((PyObject *)Py_TYPE(obj), "__name__");
    const char *utf8;

    if (name == NULL) {
        return NULL;
    }
    utf8 = PyUnicode_AsUTF8AndSize(name, NULL);
    if (utf8 == NULL) {
        Py_DECREF(name);
        return NULL;
    }
    *name_out = name;
    return utf8;
}

static Py_ssize_t
resolve_count(PyObject *n_obj, Py_ssize_t len)
{
    if (n_obj == NULL || n_obj == Py_None) {
        return len;
    }
    Py_ssize_t n = PyLong_AsSsize_t(n_obj);
    if (n == -1 && PyErr_Occurred()) {
        return -1;
    }
    return n < 0 ? 0 : n < len ? n : len;
}

/* The argument stack of a METH_FASTCALL method: nargs positional values,
 * followed by the keyword values whose names are in kwnames. */
typedef struct {
    PyObject *const *args;
    Py_ssize_t nargs;
    PyObject *kwnames;
} fastcall_stack;

/* Build the (args, kwargs) pair that PyArg_ParseTupleAndKeywords() and a Python
 * function take, from a fastcall stack. */
static PyObject *
fastcall_varargs(const fastcall_stack *st, PyObject **kwargs_out)
{
    PyObject *args_tuple = PyTuple_New(st->nargs);
    PyObject *kwargs = NULL;
    Py_ssize_t nkw = st->kwnames == NULL ? 0 : PyTuple_Size(st->kwnames);
    Py_ssize_t i;

    if (args_tuple == NULL) {
        return NULL;
    }
    for (i = 0; i < st->nargs; i++) {
        Py_INCREF(st->args[i]);
        PyTuple_SetItem(args_tuple, i, st->args[i]);
    }
    if (nkw > 0) {
        kwargs = PyDict_New();
        if (kwargs == NULL) {
            Py_DECREF(args_tuple);
            return NULL;
        }
        for (i = 0; i < nkw; i++) {
            if (PyDict_SetItem(kwargs, PyTuple_GetItem(st->kwnames, i),
                               st->args[st->nargs + i]) < 0) {
                Py_DECREF(args_tuple);
                Py_DECREF(kwargs);
                return NULL;
            }
        }
    }
    *kwargs_out = kwargs;
    return args_tuple;
}

/* Index of keyword in a NULL-terminated parameter name list, or -1 when the
 * name is not a parameter of the method.  Names are compared by length first,
 * so the cost does not grow with the keyword's position in the list. */
static Py_ssize_t
keyword_index(PyObject *keyword, char *const *names)
{
    Py_ssize_t name_len = PyUnicode_GetLength(keyword);
    Py_ssize_t i;

    if (name_len < 0) {
        return -1;
    }
    for (i = 0; names[i] != NULL; i++) {
        if ((Py_ssize_t)strlen(names[i]) == name_len
                && PyUnicode_CompareWithASCIIString(keyword, names[i]) == 0) {
            return i;
        }
    }
    return -1;
}

/* Parse the "i" format: an int, and nothing else. */
static int
py_long_as_int(PyObject *value, int *out)
{
    int overflow = 0;
    long result = PyLong_AsLongAndOverflow(value, &overflow);

    if ((result == -1 && PyErr_Occurred()) || overflow != 0) {
        return -1;
    }
    *out = (int)result;
    return 0;
}

/* Parse the "n" format: a Py_ssize_t. */
static int
py_long_as_ssize(PyObject *value, Py_ssize_t *out)
{
    Py_ssize_t result = PyLong_AsSsize_t(value);

    if (result == -1 && PyErr_Occurred()) {
        return -1;
    }
    *out = result;
    return 0;
}

/* Parse the "p" format: a truth value. */
static int
py_object_as_bool(PyObject *value, int *out)
{
    int truth = PyObject_IsTrue(value);

    if (truth < 0) {
        return -1;
    }
    *out = truth;
    return 0;
}

/* Call the Python implementation with the arguments this call received.  The
 * (args, kwargs) pair is built only here, on the paths that hand work back to
 * Python, so the parsed fast path never builds it. */
static PyObject *
call_python_function(const char *module_name, const char *function_name,
                     const fastcall_stack *st)
{
    PyObject *kwargs = NULL;
    PyObject *args = fastcall_varargs(st, &kwargs);
    PyObject *module;
    PyObject *function;
    PyObject *result;

    if (args == NULL) {
        return NULL;
    }
    module = PyImport_ImportModule(module_name);
    if (module == NULL) {
        Py_DECREF(args);
        Py_XDECREF(kwargs);
        return NULL;
    }
    function = PyObject_GetAttrString(module, function_name);
    Py_DECREF(module);
    if (function == NULL) {
        Py_DECREF(args);
        Py_XDECREF(kwargs);
        return NULL;
    }
    result = PyObject_Call(function, args, kwargs);
    Py_DECREF(function);
    Py_DECREF(args);
    Py_XDECREF(kwargs);
    return result;
}

static int
control_codes_mode(PyObject *obj)
{
    if (obj == NULL || obj == Py_None) {
        return WCWIDTH_PARSE;
    }
    if (!PyUnicode_Check(obj)) {
        PyErr_SetString(PyExc_TypeError, "control_codes must be a string");
        return -1;
    }
    /* Compare with an explicit length: a Python str may contain NUL, and
     * PyUnicode_AsUTF8() would silently cut the value there -- selecting a
     * different mode than the caller passed. */
    Py_ssize_t value_len = 0;
    const char *value = PyUnicode_AsUTF8AndSize(obj, &value_len);
    if (value == NULL) {
        return -1;
    }
    if (value_len == 6 && memcmp(value, "ignore", 6) == 0) {
        return WCWIDTH_IGNORE;
    }
    if (value_len == 6 && memcmp(value, "strict", 6) == 0) {
        return WCWIDTH_STRICT;
    }
    return WCWIDTH_PARSE;
}

static const char *
width_error_message(int error)
{
    switch (error) {
    case WCWIDTH_ERROR_INDETERMINATE:
        return "Indeterminate cursor sequence";
    case WCWIDTH_ERROR_ILLEGAL_CTRL:
        return "Illegal control character";
    case WCWIDTH_ERROR_VERTICAL_CTRL:
        return "Vertical movement character";
    case WCWIDTH_ERROR_CURSOR_LEFT_EXCEED:
        return "Cursor left movement would exceed the start of the line";
    case WCWIDTH_ERROR_CURSOR_LEFT_ABSOLUTE:
        return "Indeterminate horizontal position (absolute column unknown)";
    case WCWIDTH_ERROR_HORIZONTAL_MOVEMENT:
        return "Horizontal movement from an indeterminate starting column";
    default:
        return "control character with indeterminate effect";
    }
}

static int
unicode_to_utf8(PyObject *text_obj, const char **text, Py_ssize_t *text_len)
{
    *text = PyUnicode_AsUTF8AndSize(text_obj, text_len);
    if (*text != NULL) {
        return 0;
    }
    if (PyErr_ExceptionMatches(PyExc_UnicodeEncodeError)) {
        PyErr_Clear();
        return -1;
    }
    return -1;
}

static int
fillchar_utf8(PyObject *fillchar_obj, const char **fillchar, size_t *fillchar_len)
{
    if (fillchar_obj == NULL) {
        *fillchar = " ";
        *fillchar_len = 1;
        return 0;
    }
    if (!PyUnicode_Check(fillchar_obj)) {
        return -1;
    }
    Py_ssize_t len;
    *fillchar = PyUnicode_AsUTF8AndSize(fillchar_obj, &len);
    if (*fillchar == NULL) {
        if (PyErr_ExceptionMatches(PyExc_UnicodeEncodeError)) {
            PyErr_Clear();
            return -1;
        }
        return -1;
    }
    *fillchar_len = (size_t)len;
    return 0;
}

/* Mirror _constants.py resolve_terminal(): True/auto resolves via the
 * TERM_PROGRAM/TERM env vars, False/None/'' means no lookup, and non-str
 * values raise the same AttributeError as term_program.strip(). */
static const char *
term_program_cstr(PyObject *obj, int default_auto_detect)
{
    if (obj == NULL) {
        if (!default_auto_detect) {
            return NULL;
        }
        obj = Py_True;
    }
    if (obj == Py_None) {
        return NULL;
    }
    if (PyBool_Check(obj)) {
        if (obj == Py_False) {
            return NULL;
        }
        const char *tprog = getenv("TERM_PROGRAM");
        if (tprog != NULL && tprog[0] != '\0') {
            return tprog;
        }
        return getenv("TERM");
    }
    if (PyUnicode_Check(obj)) {
        Py_ssize_t name_len = 0;
        const char *name;

        if (PyUnicode_GetLength(obj) == 0) {
            return NULL;
        }
        name = PyUnicode_AsUTF8AndSize(obj, &name_len);
        if (name == NULL) {
            return NULL;
        }
        /* An embedded NUL would truncate the name and silently select a
         * different terminal's override table, so treat it as no match. */
        if (memchr(name, '\0', (size_t) name_len) != NULL) {
            return NULL;
        }
        return name;
    }
    PyObject *type_name = NULL;
    const char *name = type_name_utf8(obj, &type_name);

    if (name == NULL) {
        return NULL;
    }
    PyErr_Format(PyExc_AttributeError,
                 "'%s' object has no attribute 'strip'", name);
    Py_DECREF(type_name);
    return NULL;
}

/*
 * PyArg_Parse converter for ambiguous_width.
 *
 * East Asian Ambiguous is narrow or wide and nothing else (UAX #11), so any
 * other value is clamped into range rather than raising: width measurement is
 * called from rendering hot loops, and a new exception path there would break
 * callers passing a computed value.
 *
 * Parsing through a converter rather than the "i" format also keeps a value
 * beyond INT_MAX from raising OverflowError before the clamp can run.
 */
static int
convert_ambiguous_width(PyObject *obj, void *addr)
{
    int *out = (int *) addr;
    int overflow = 0;
    long value;

    if (obj == NULL) {
        return 1;
    }
    value = PyLong_AsLongAndOverflow(obj, &overflow);
    if (value == -1 && PyErr_Occurred()) {
        return 0; /* not an integer: let the TypeError stand */
    }
    if (overflow > 0) {
        *out = 2;
    }
    else if (overflow < 0) {
        *out = 1;
    }
    else {
        *out = (value < 1) ? 1 : ((value > 2) ? 2 : (int) value);
    }
    return 1;
}

static PyObject *
wcwidth_impl(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *wc_obj = NULL;
    PyObject *dummy_unicode_version = NULL;
    int ambiguous_width = 1;
    static char *kwlist[] = {"wc", "unicode_version", "ambiguous_width", NULL};
    fastcall_stack st = {args, nargs, kwnames};
    Py_ssize_t i, nkw;

    (void)self;
    if (nargs > 3) {
        goto reject;
    }
    if (nargs > 0) {
        wc_obj = args[0];
    }
    if (nargs > 1) {
        dummy_unicode_version = args[1];
    }
    if (nargs > 2 && !convert_ambiguous_width(args[2], &ambiguous_width)) {
        goto reject;
    }
    nkw = kwnames == NULL ? 0 : PyTuple_Size(kwnames);
    for (i = 0; i < nkw; i++) {
        PyObject *value = args[nargs + i];
        switch (keyword_index(PyTuple_GetItem(kwnames, i), kwlist)) {
        case 0:  /* wc */
            if (nargs > 0) {
                goto reject;
            }
            wc_obj = value;
            break;
        case 1:  /* unicode_version */
            dummy_unicode_version = value;
            break;
        case 2:  /* ambiguous_width */
            if (!convert_ambiguous_width(value, &ambiguous_width)) {
                goto reject;
            }
            break;
        default:
            goto reject;
        }
    }
    if (wc_obj == NULL) {
        goto reject;
    }

    int truthy = PyObject_IsTrue(wc_obj);
    if (truthy < 0) {
        return NULL;
    }
    uint32_t ucs = 0;
    if (truthy) {
        if (!PyUnicode_Check(wc_obj)) {
            PyObject *type_name = NULL;
            const char *name = type_name_utf8(wc_obj, &type_name);

            if (name == NULL) {
                return NULL;
            }
            PyErr_Format(PyExc_TypeError,
                         "ord() expected a character, but object of type '%s' found",
                         name);
            Py_DECREF(type_name);
            return NULL;
        }
        Py_ssize_t char_count = PyUnicode_GetLength(wc_obj);
        if (char_count != 1) {
            PyErr_Format(PyExc_TypeError,
                         "ord() expected a character, but string of length %zd found",
                         char_count);
            return NULL;
        }
        ucs = PyUnicode_ReadChar(wc_obj, 0);
    }

    int result = wcwidth_u32(ucs, ambiguous_width);
    return PyLong_FromLong(result);

reject:
    {
        /* Not a valid call: the parser below reports it. */
        PyObject *kwargs = NULL;
        PyObject *callargs = fastcall_varargs(&st, &kwargs);

        if (callargs != NULL) {
            PyErr_Clear();
            (void)PyArg_ParseTupleAndKeywords(callargs, kwargs, "O|OO&", kwlist,
                                              &wc_obj, &dummy_unicode_version,
                                              convert_ambiguous_width, &ambiguous_width);
            Py_DECREF(callargs);
            Py_XDECREF(kwargs);
        }
        return NULL;
    }
}

static PyObject *
wcswidth_impl(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *pwcs_obj = NULL;
    PyObject *n_obj = NULL;
    PyObject *dummy_unicode_version = NULL;
    int ambiguous_width = 1;
    static char *kwlist[] = {"pwcs", "n", "unicode_version", "ambiguous_width", NULL};
    fastcall_stack st = {args, nargs, kwnames};
    Py_ssize_t i, nkw;

    (void)self;
    if (nargs > 4) {
        goto reject;
    }
    if (nargs > 0) {
        if (!PyUnicode_Check(args[0])) {
            goto reject;
        }
        pwcs_obj = args[0];
    }
    if (nargs > 1) {
        n_obj = args[1];
    }
    if (nargs > 2) {
        dummy_unicode_version = args[2];
    }
    if (nargs > 3 && !convert_ambiguous_width(args[3], &ambiguous_width)) {
        goto reject;
    }
    nkw = kwnames == NULL ? 0 : PyTuple_Size(kwnames);
    for (i = 0; i < nkw; i++) {
        PyObject *value = args[nargs + i];
        switch (keyword_index(PyTuple_GetItem(kwnames, i), kwlist)) {
        case 0:  /* pwcs */
            if (nargs > 0 || !PyUnicode_Check(value)) {
                goto reject;
            }
            pwcs_obj = value;
            break;
        case 1:  /* n */
            n_obj = value;
            break;
        case 2:  /* unicode_version */
            dummy_unicode_version = value;
            break;
        case 3:  /* ambiguous_width */
            if (!convert_ambiguous_width(value, &ambiguous_width)) {
                goto reject;
            }
            break;
        default:
            goto reject;
        }
    }
    if (pwcs_obj == NULL) {
        goto reject;
    }

    Py_ssize_t len;
    uint32_t *codepoints = unicode_codepoints(pwcs_obj, &len);
    if (codepoints == NULL) {
        return NULL;
    }

    Py_ssize_t count = resolve_count(n_obj, len);
    if (count < 0) {
        PyMem_Free(codepoints);
        return NULL;
    }

    int result = wcswidth_u32(codepoints, (size_t)count, ambiguous_width);
    PyMem_Free(codepoints);
    return PyLong_FromLong(result);

reject:
    {
        /* Not a valid call: the parser below reports it. */
        PyObject *kwargs = NULL;
        PyObject *callargs = fastcall_varargs(&st, &kwargs);

        if (callargs != NULL) {
            PyErr_Clear();
            (void)PyArg_ParseTupleAndKeywords(callargs, kwargs, "U|OOO&", kwlist,
                                              &pwcs_obj, &n_obj, &dummy_unicode_version,
                                              convert_ambiguous_width, &ambiguous_width);
            Py_DECREF(callargs);
            Py_XDECREF(kwargs);
        }
        return NULL;
    }
}

static PyObject *
wcstwidth_impl(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *pwcs_obj = NULL;
    PyObject *n_obj = NULL;
    PyObject *dummy_unicode_version = NULL;
    int ambiguous_width = 1;
    PyObject *term_program_obj = NULL;
    static char *kwlist[] = {"pwcs", "n", "unicode_version", "ambiguous_width",
                             "term_program", NULL};
    fastcall_stack st = {args, nargs, kwnames};
    Py_ssize_t i, nkw;

    (void)self;
    if (nargs > 5) {
        goto reject;
    }
    if (nargs > 0) {
        if (!PyUnicode_Check(args[0])) {
            goto reject;
        }
        pwcs_obj = args[0];
    }
    if (nargs > 1) {
        n_obj = args[1];
    }
    if (nargs > 2) {
        dummy_unicode_version = args[2];
    }
    if (nargs > 3 && !convert_ambiguous_width(args[3], &ambiguous_width)) {
        goto reject;
    }
    if (nargs > 4) {
        term_program_obj = args[4];
    }
    nkw = kwnames == NULL ? 0 : PyTuple_Size(kwnames);
    for (i = 0; i < nkw; i++) {
        PyObject *value = args[nargs + i];
        switch (keyword_index(PyTuple_GetItem(kwnames, i), kwlist)) {
        case 0:  /* pwcs */
            if (nargs > 0 || !PyUnicode_Check(value)) {
                goto reject;
            }
            pwcs_obj = value;
            break;
        case 1:  /* n */
            n_obj = value;
            break;
        case 2:  /* unicode_version */
            dummy_unicode_version = value;
            break;
        case 3:  /* ambiguous_width */
            if (!convert_ambiguous_width(value, &ambiguous_width)) {
                goto reject;
            }
            break;
        case 4:  /* term_program */
            term_program_obj = value;
            break;
        default:
            goto reject;
        }
    }
    if (pwcs_obj == NULL) {
        goto reject;
    }

    const char *term_program = term_program_cstr(term_program_obj, 1);
    if (term_program == NULL && PyErr_Occurred()) {
        return NULL;
    }

    Py_ssize_t len;
    uint32_t *codepoints = unicode_codepoints(pwcs_obj, &len);
    if (codepoints == NULL) {
        return NULL;
    }

    Py_ssize_t count = resolve_count(n_obj, len);
    if (count < 0) {
        PyMem_Free(codepoints);
        return NULL;
    }

    int result = wcstwidth_u32(codepoints, (size_t)count, ambiguous_width, term_program);
    PyMem_Free(codepoints);
    return PyLong_FromLong(result);

reject:
    {
        /* Not a valid call: the parser below reports it. */
        PyObject *kwargs = NULL;
        PyObject *callargs = fastcall_varargs(&st, &kwargs);

        if (callargs != NULL) {
            PyErr_Clear();
            (void)PyArg_ParseTupleAndKeywords(callargs, kwargs, "U|OOO&O", kwlist,
                                              &pwcs_obj, &n_obj, &dummy_unicode_version,
                                              convert_ambiguous_width, &ambiguous_width,
                                              &term_program_obj);
            Py_DECREF(callargs);
            Py_XDECREF(kwargs);
        }
        return NULL;
    }
}

static PyObject *
width_impl(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *text_obj = NULL;
    PyObject *control_codes_obj = NULL;
    int tabsize = 8;
    int ambiguous_width = 1;
    PyObject *term_program_obj = NULL;
    static char *kwlist[] = {"text", "control_codes", "tabsize", "ambiguous_width",
                             "term_program", NULL};
    fastcall_stack st = {args, nargs, kwnames};
    Py_ssize_t i, nkw;

    (void)self;
    if (nargs > 1) {
        goto reject;
    }
    if (nargs > 0) {
        if (!PyUnicode_Check(args[0])) {
            goto reject;
        }
        text_obj = args[0];
    }
    nkw = kwnames == NULL ? 0 : PyTuple_Size(kwnames);
    for (i = 0; i < nkw; i++) {
        PyObject *value = args[nargs + i];
        switch (keyword_index(PyTuple_GetItem(kwnames, i), kwlist)) {
        case 0:  /* text */
            if (nargs > 0 || !PyUnicode_Check(value)) {
                goto reject;
            }
            text_obj = value;
            break;
        case 1:  /* control_codes */
            control_codes_obj = value;
            break;
        case 2:  /* tabsize */
            if (py_long_as_int(value, &tabsize) < 0) {
                goto reject;
            }
            break;
        case 3:  /* ambiguous_width */
            if (!convert_ambiguous_width(value, &ambiguous_width)) {
                goto reject;
            }
            break;
        case 4:  /* term_program */
            term_program_obj = value;
            break;
        default:
            goto reject;
        }
    }
    if (text_obj == NULL) {
        goto reject;
    }

    const char *term_program = term_program_cstr(term_program_obj, 0);
    if (term_program == NULL && PyErr_Occurred()) {
        return NULL;
    }

    int mode = control_codes_mode(control_codes_obj);
    if (mode < 0) {
        return NULL;
    }
    /* 'strict' mode routes to the Python implementation: the C library cannot
     * reproduce the ValueError messages for invalid text-sizing parameters,
     * which embed the offending value. */
    if (mode == WCWIDTH_STRICT) {
        return call_python_function("wcwidth._width", "width", &st);
    }

    Py_ssize_t len;
    uint32_t *codepoints = unicode_codepoints(text_obj, &len);
    if (codepoints == NULL) {
        return NULL;
    }

    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    opts.tabsize = tabsize;
    opts.ambiguous_width = ambiguous_width;
    opts.term_program = term_program;

    int error = 0;
    int result = wcwidth_width_u32(codepoints, (size_t)len, (wcwidth_control_mode_t)mode, &opts, &error);
    PyMem_Free(codepoints);

    if (error) {
        PyErr_SetString(PyExc_ValueError, width_error_message(error));
        return NULL;
    }
    return PyLong_FromLong(result);

reject:
    {
        /* The format accepts more positional arguments than the API does, so a
         * parse that succeeds here becomes the positional-count error. */
        PyObject *kwargs = NULL;
        PyObject *callargs = fastcall_varargs(&st, &kwargs);

        if (callargs != NULL) {
            PyErr_Clear();
            if (PyArg_ParseTupleAndKeywords(callargs, kwargs, "U|OiO&O", kwlist,
                                            &text_obj, &control_codes_obj, &tabsize,
                                            convert_ambiguous_width, &ambiguous_width,
                                            &term_program_obj)) {
                PyErr_Format(PyExc_TypeError,
                             "width() takes 1 positional argument but %zd were given",
                             nargs);
            }
            Py_DECREF(callargs);
            Py_XDECREF(kwargs);
        }
        return NULL;
    }
}

static PyObject *
align_impl(const char *name, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *text_obj = NULL;
    Py_ssize_t dest_width = 0;
    int have_dest_width = 0;
    PyObject *fillchar_obj = NULL;
    PyObject *control_codes_obj = NULL;
    int ambiguous_width = 1;
    PyObject *term_program_obj = NULL;
    static char *kwlist[] = {"text", "dest_width", "fillchar", "control_codes",
                             "ambiguous_width", "term_program", NULL};
    fastcall_stack st = {args, nargs, kwnames};
    Py_ssize_t i, nkw;

    if (nargs > 3) {
        goto reject;
    }
    if (nargs > 0) {
        if (!PyUnicode_Check(args[0])) {
            goto reject;
        }
        text_obj = args[0];
    }
    if (nargs > 1) {
        if (py_long_as_ssize(args[1], &dest_width) < 0) {
            goto reject;
        }
        have_dest_width = 1;
    }
    if (nargs > 2) {
        fillchar_obj = args[2];
    }
    nkw = kwnames == NULL ? 0 : PyTuple_Size(kwnames);
    for (i = 0; i < nkw; i++) {
        PyObject *value = args[nargs + i];
        switch (keyword_index(PyTuple_GetItem(kwnames, i), kwlist)) {
        case 0:  /* text */
            if (nargs > 0 || !PyUnicode_Check(value)) {
                goto reject;
            }
            text_obj = value;
            break;
        case 1:  /* dest_width */
            if (py_long_as_ssize(value, &dest_width) < 0) {
                goto reject;
            }
            have_dest_width = 1;
            break;
        case 2:  /* fillchar */
            fillchar_obj = value;
            break;
        case 3:  /* control_codes */
            control_codes_obj = value;
            break;
        case 4:  /* ambiguous_width */
            if (!convert_ambiguous_width(value, &ambiguous_width)) {
                goto reject;
            }
            break;
        case 5:  /* term_program */
            term_program_obj = value;
            break;
        default:
            goto reject;
        }
    }
    if (text_obj == NULL || !have_dest_width) {
        goto reject;
    }

    const char *term_program = term_program_cstr(term_program_obj, 0);
    if (term_program == NULL && PyErr_Occurred()) {
        return NULL;
    }
    int mode = control_codes_mode(control_codes_obj);
    if (mode < 0) {
        return NULL;
    }
    /* 'strict' mode routes to the Python implementation, for the same reason
     * width_impl() does: the C library reports a wcwidth_error_t code, not the
     * ValueError messages that name the offending character, position, and
     * text-sizing value.  Without this, a strict violation inside ljust() /
     * rjust() / center() is padded and returned instead of raised. */
    if (mode == WCWIDTH_STRICT) {
        return call_python_function("wcwidth.align", name, &st);
    }

    size_t padded_width = dest_width > 0 ? (size_t)dest_width : 0;

    const char *text;
    Py_ssize_t text_len;
    if (unicode_to_utf8(text_obj, &text, &text_len) < 0) {
        /* unicode_to_utf8() clears only UnicodeEncodeError; anything else
         * (MemoryError, for instance) is still live, and calling into Python
         * with it set raises SystemError from the interpreter. */
        if (PyErr_Occurred()) {
            return NULL;
        }
        return call_python_function("wcwidth.align", name, &st);
    }
    const char *fillchar;
    size_t fillchar_len;
    if (fillchar_utf8(fillchar_obj, &fillchar, &fillchar_len) < 0) {
        if (PyErr_Occurred()) {
            return NULL;
        }
        return call_python_function("wcwidth.align", name, &st);
    }

    wcwidth_align_opts_t opts = WCWIDTH_ALIGN_OPTS_DEFAULT;
    opts.dest_width = padded_width;
    opts.fillchar = fillchar;
    opts.fillchar_len = fillchar_len;
    opts.ambiguous_width = ambiguous_width;
    opts.term_program = term_program;

    int error = WCWIDTH_ERROR_NONE;
    size_t out_len = 0;
    char *out;
    if (strcmp(name, "ljust") == 0) {
        out = wcwidth_ljust_u8(text, (size_t)text_len, (wcwidth_control_mode_t)mode, &opts,
                               &out_len, &error);
    } else if (strcmp(name, "rjust") == 0) {
        out = wcwidth_rjust_u8(text, (size_t)text_len, (wcwidth_control_mode_t)mode, &opts,
                               &out_len, &error);
    } else {
        out = wcwidth_center_u8(text, (size_t)text_len, (wcwidth_control_mode_t)mode, &opts,
                                &out_len, &error);
    }
    if (out == NULL) {
        if (error != WCWIDTH_ERROR_NONE) {
            PyErr_SetString(PyExc_ValueError, width_error_message(error));
        } else {
            PyErr_NoMemory();
        }
        return NULL;
    }
    PyObject *result = PyUnicode_FromStringAndSize(out, (Py_ssize_t)out_len);
    free(out);
    return result;

reject:
    {
        /* The format accepts more positional arguments than the API does, so a
         * parse that succeeds here becomes the positional-count error. */
        PyObject *kwargs = NULL;
        PyObject *callargs = fastcall_varargs(&st, &kwargs);

        if (callargs != NULL) {
            PyErr_Clear();
            if (PyArg_ParseTupleAndKeywords(callargs, kwargs, "Un|OOO&O", kwlist,
                                            &text_obj, &dest_width, &fillchar_obj,
                                            &control_codes_obj, convert_ambiguous_width,
                                            &ambiguous_width, &term_program_obj)) {
                PyErr_Format(PyExc_TypeError,
                             "%s() takes 3 positional arguments but %zd were given",
                             name, nargs);
            }
            Py_DECREF(callargs);
            Py_XDECREF(kwargs);
        }
        return NULL;
    }
}

static PyObject *
ljust_impl(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return align_impl("ljust", args, nargs, kwnames);
}

static PyObject *
rjust_impl(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return align_impl("rjust", args, nargs, kwnames);
}

static PyObject *
center_impl(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    return align_impl("center", args, nargs, kwnames);
}

static PyObject *
strip_sequences_impl(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *text_obj = NULL;
    static char *kwlist[] = {"text", NULL};
    fastcall_stack st = {args, nargs, kwnames};
    Py_ssize_t i, nkw;

    (void)self;
    if (nargs > 1) {
        goto reject;
    }
    if (nargs > 0) {
        if (!PyUnicode_Check(args[0])) {
            goto reject;
        }
        text_obj = args[0];
    }
    nkw = kwnames == NULL ? 0 : PyTuple_Size(kwnames);
    for (i = 0; i < nkw; i++) {
        PyObject *value = args[nargs + i];
        switch (keyword_index(PyTuple_GetItem(kwnames, i), kwlist)) {
        case 0:  /* text */
            if (nargs > 0 || !PyUnicode_Check(value)) {
                goto reject;
            }
            text_obj = value;
            break;
        default:
            goto reject;
        }
    }
    if (text_obj == NULL) {
        goto reject;
    }

    const char *text;
    Py_ssize_t text_len;
    if (unicode_to_utf8(text_obj, &text, &text_len) < 0) {
        if (PyErr_Occurred()) {
            return NULL;
        }
        return call_python_function("wcwidth.escape_sequences", "strip_sequences", &st);
    }

    size_t out_len = 0;
    size_t needed = wcwidth_escape_strip(text, (size_t)text_len, NULL, 0, &out_len);
    char *out = PyMem_Malloc(needed + 1);
    if (out == NULL) {
        return PyErr_NoMemory();
    }
    wcwidth_escape_strip(text, (size_t)text_len, out, needed + 1, &out_len);
    PyObject *result = PyUnicode_FromStringAndSize(out, (Py_ssize_t)out_len);
    PyMem_Free(out);
    return result;

reject:
    {
        /* Not a valid call: the parser below reports it. */
        PyObject *kwargs = NULL;
        PyObject *callargs = fastcall_varargs(&st, &kwargs);

        if (callargs != NULL) {
            PyErr_Clear();
            (void)PyArg_ParseTupleAndKeywords(callargs, kwargs, "U", kwlist, &text_obj);
            Py_DECREF(callargs);
            Py_XDECREF(kwargs);
        }
        return NULL;
    }
}

static PyObject *
propagate_sgr_impl(PyObject *self, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *lines_obj = NULL;
    static char *kwlist[] = {"lines", NULL};
    fastcall_stack st = {args, nargs, kwnames};
    Py_ssize_t i, nkw;

    (void)self;
    if (nargs > 1) {
        goto reject;
    }
    if (nargs > 0) {
        lines_obj = args[0];
    }
    nkw = kwnames == NULL ? 0 : PyTuple_Size(kwnames);
    for (i = 0; i < nkw; i++) {
        PyObject *value = args[nargs + i];
        switch (keyword_index(PyTuple_GetItem(kwnames, i), kwlist)) {
        case 0:  /* lines */
            if (nargs > 0) {
                goto reject;
            }
            lines_obj = value;
            break;
        default:
            goto reject;
        }
    }
    if (lines_obj == NULL) {
        goto reject;
    }

    PyObject *fast = PySequence_Fast(lines_obj, "lines must be an iterable of strings");
    if (fast == NULL) {
        return NULL;
    }
    /* PySequence_Fast() returns a list for a list input and a tuple for a tuple
     * input, so both accessor families are needed.  PyList_GetItem() and
     * PyTuple_GetItem() return borrowed references. */
    int fast_is_list = PyList_Check(fast);
    Py_ssize_t nlines = fast_is_list ? PyList_Size(fast) : PyTuple_Size(fast);
    if (nlines == 0) {
        Py_DECREF(fast);
        return PyList_New(0);
    }

    char **c_lines = PyMem_Malloc((size_t)nlines * sizeof(char *));
    size_t *c_line_lens = PyMem_Malloc((size_t)nlines * sizeof(size_t));
    size_t *c_out_lens = PyMem_Malloc((size_t)nlines * sizeof(size_t));
    if (c_lines == NULL || c_line_lens == NULL || c_out_lens == NULL) {
        PyMem_Free(c_lines);
        PyMem_Free(c_line_lens);
        PyMem_Free(c_out_lens);
        Py_DECREF(fast);
        return PyErr_NoMemory();
    }

    PyObject *result = NULL;
    for (i = 0; i < nlines; i++) {
        PyObject *line = fast_is_list ? PyList_GetItem(fast, i) : PyTuple_GetItem(fast, i);
        const char *utf8;
        Py_ssize_t utf8_len;
        if (unicode_to_utf8(line, &utf8, &utf8_len) < 0) {
            while (i > 0) {
                PyMem_Free(c_lines[--i]);
            }
            PyMem_Free(c_lines);
            PyMem_Free(c_line_lens);
            PyMem_Free(c_out_lens);
            Py_DECREF(fast);
            if (PyErr_Occurred()) {
                return NULL;
            }
            return call_python_function("wcwidth.sgr_state", "propagate_sgr", &st);
        }
        char *buf = PyMem_Malloc((size_t)utf8_len + WCWIDTH_SGR_PROPAGATE_SPARE + 1);
        if (buf == NULL) {
            Py_DECREF(fast);
            while (i > 0) {
                PyMem_Free(c_lines[--i]);
            }
            PyMem_Free(c_lines);
            PyMem_Free(c_line_lens);
            PyMem_Free(c_out_lens);
            return PyErr_NoMemory();
        }
        memcpy(buf, utf8, (size_t)utf8_len);
        buf[utf8_len] = '\0';
        c_lines[i] = buf;
        c_line_lens[i] = (size_t)utf8_len;
    }

    /* The C library can still fail for an SGR state beyond its reserved
     * prefix space; fall back to the Python implementation in that case. */
    if (wcwidth_sgr_propagate(c_lines, c_line_lens, c_out_lens, (size_t)nlines) < 0) {
        PyErr_Clear();
        result = call_python_function("wcwidth.sgr_state", "propagate_sgr", &st);
    } else {
        result = PyList_New(nlines);
        if (result != NULL) {
            for (i = 0; i < nlines; i++) {
                PyObject *line = PyUnicode_FromStringAndSize(c_lines[i],
                                                             (Py_ssize_t)c_out_lens[i]);
                if (line == NULL) {
                    Py_DECREF(result);
                    result = NULL;
                    break;
                }
                if (PyList_SetItem(result, i, line) < 0) {
                    /* SetItem() steals the reference whether or not it fails */
                    Py_DECREF(result);
                    result = NULL;
                    break;
                }
            }
        }
    }

    for (i = 0; i < nlines; i++) {
        PyMem_Free(c_lines[i]);
    }
    PyMem_Free(c_lines);
    PyMem_Free(c_line_lens);
    PyMem_Free(c_out_lens);
    Py_DECREF(fast);
    return result;

reject:
    {
        /* Not a valid call: the parser below reports it. */
        PyObject *kwargs = NULL;
        PyObject *callargs = fastcall_varargs(&st, &kwargs);

        if (callargs != NULL) {
            PyErr_Clear();
            (void)PyArg_ParseTupleAndKeywords(callargs, kwargs, "O", kwlist, &lines_obj);
            Py_DECREF(callargs);
            Py_XDECREF(kwargs);
        }
        return NULL;
    }
}

/*
 * Grapheme cluster iteration.
 *
 * libwcwidth segments UTF-8 buffers, so the input string is encoded once and
 * each cluster is decoded back into a str as it is yielded.  The iterator owns
 * the bytes object: wcwidth_grapheme_next() returns pointers into that buffer,
 * so it must outlive the iteration.
 *
 * Laziness is preserved -- the Python implementation is a generator, and code
 * that breaks out early (a clip that stops at a column, say) must not pay to
 * segment the whole string.
 */
typedef struct {
    PyObject_HEAD
    PyObject *utf8;
    wcwidth_grapheme_iter_t *iter;
} grapheme_iterator;

/*
 * The iterator is a heap type, so it lives in per-module state rather than as
 * a static type: static types are shared between subinterpreters, which would
 * contradict Py_MOD_PER_INTERPRETER_GIL_SUPPORTED below.
 */
typedef struct {
    PyTypeObject *grapheme_iterator_type;
} module_state;

static void
grapheme_iterator_release(grapheme_iterator *self)
{
    if (self->iter != NULL) {
        wcwidth_grapheme_iter_free(self->iter);
        self->iter = NULL;
    }
    Py_CLEAR(self->utf8);
}

static int
grapheme_iterator_traverse(PyObject *op, visitproc visit, void *arg)
{
    grapheme_iterator *self = (grapheme_iterator *)op;
    Py_VISIT(Py_TYPE(op));
    Py_VISIT(self->utf8);
    return 0;
}

static int
grapheme_iterator_clear(PyObject *op)
{
    grapheme_iterator_release((grapheme_iterator *)op);
    return 0;
}

static void
grapheme_iterator_dealloc(PyObject *op)
{
    PyTypeObject *type = Py_TYPE(op);
    freefunc tp_free;

    PyObject_GC_UnTrack(op);
    grapheme_iterator_release((grapheme_iterator *)op);
    /* tp_free is hidden by the limited API; PyType_GetSlot() reads it. */
    tp_free = (freefunc)PyType_GetSlot(type, Py_tp_free);
    tp_free(op);
    /* instances of a heap type hold a reference to it */
    Py_DECREF(type);
}

static PyObject *
grapheme_iterator_next(PyObject *op)
{
    grapheme_iterator *self = (grapheme_iterator *)op;
    const char *cluster;
    size_t cluster_len = 0;

    if (self->iter == NULL) {
        return NULL;
    }
    cluster = wcwidth_grapheme_next(self->iter, &cluster_len);
    if (cluster == NULL) {
        /* exhausted: drop the buffer now rather than at dealloc */
        grapheme_iterator_release(self);
        return NULL;
    }
    return PyUnicode_DecodeUTF8(cluster, (Py_ssize_t)cluster_len, NULL);
}

static PyType_Slot grapheme_iterator_slots[] = {
    {Py_tp_dealloc, (void *)grapheme_iterator_dealloc},
    {Py_tp_traverse, (void *)grapheme_iterator_traverse},
    {Py_tp_clear, (void *)grapheme_iterator_clear},
    {Py_tp_iter, (void *)PyObject_SelfIter},
    {Py_tp_iternext, (void *)grapheme_iterator_next},
    {Py_tp_doc, (void *)"Iterator over grapheme clusters, backed by libwcwidth."},
    {0, NULL},
};

#if PY_VERSION_HEX >= 0x030A0000
#define WCWIDTH_ITERATOR_FLAGS (Py_TPFLAGS_DISALLOW_INSTANTIATION | Py_TPFLAGS_IMMUTABLETYPE)
#else
#define WCWIDTH_ITERATOR_FLAGS 0
#endif

static PyType_Spec grapheme_iterator_spec = {
    "wcwidth._wcwidth_c._grapheme_iterator",
    sizeof(grapheme_iterator),
    0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | WCWIDTH_ITERATOR_FLAGS,
    grapheme_iterator_slots,
};

static PyObject *
iter_graphemes_impl(PyObject *module, PyObject *const *args, Py_ssize_t nargs,
                    PyObject *kwnames)
{
    static char *keywords[] = {"unistr", "start", "end", NULL};
    PyObject *unistr = NULL;
    PyObject *start = NULL;
    PyObject *end = NULL;
    PyObject *utf8;
    module_state *state;
    grapheme_iterator *self;
    PyTypeObject *type;
    allocfunc alloc_func;
    fastcall_stack st = {args, nargs, kwnames};
    Py_ssize_t i, nkw;

    if (nargs > 3) {
        goto reject;
    }
    if (nargs > 0) {
        unistr = args[0];
    }
    if (nargs > 1) {
        start = args[1];
    }
    if (nargs > 2) {
        end = args[2];
    }
    nkw = kwnames == NULL ? 0 : PyTuple_Size(kwnames);
    for (i = 0; i < nkw; i++) {
        PyObject *value = args[nargs + i];
        switch (keyword_index(PyTuple_GetItem(kwnames, i), keywords)) {
        case 0:  /* unistr */
            if (nargs > 0) {
                goto reject;
            }
            unistr = value;
            break;
        case 1:  /* start */
            start = value;
            break;
        case 2:  /* end */
            end = value;
            break;
        default:
            goto reject;
        }
    }
    if (unistr == NULL) {
        goto reject;
    }

    /*
     * 'start' and 'end' are codepoint indices, while the C library segments a
     * whole buffer; rather than re-deriving the Python slicing semantics here,
     * those calls go to the Python implementation.
     */
    if (start != NULL || end != NULL || !PyUnicode_Check(unistr)) {
        return call_python_function("wcwidth.grapheme", "iter_graphemes", &st);
    }

    utf8 = PyUnicode_AsUTF8String(unistr);
    if (utf8 == NULL) {
        /* lone surrogates have no UTF-8 form; Python segments them fine */
        PyErr_Clear();
        return call_python_function("wcwidth.grapheme", "iter_graphemes", &st);
    }

    state = (module_state *)PyModule_GetState(module);
    if (state == NULL || state->grapheme_iterator_type == NULL) {
        Py_DECREF(utf8);
        PyErr_SetString(PyExc_SystemError, "wcwidth._wcwidth_c module state is missing");
        return NULL;
    }

    type = state->grapheme_iterator_type;
    /* tp_alloc is hidden by the limited API; PyType_GetSlot() reads it. */
    alloc_func = (allocfunc)PyType_GetSlot(type, Py_tp_alloc);
    self = (grapheme_iterator *)alloc_func(type, 0);
    if (self == NULL) {
        Py_DECREF(utf8);
        return NULL;
    }

    self->iter = wcwidth_grapheme_iter_new(PyBytes_AsString(utf8),
                                           (size_t)PyBytes_Size(utf8));
    if (self->iter == NULL) {
        self->utf8 = NULL;
        Py_DECREF(self);
        Py_DECREF(utf8);
        return PyErr_NoMemory();
    }
    self->utf8 = utf8;  /* steals the reference */
    return (PyObject *)self;

reject:
    {
        /* Not a valid call: the parser below reports it. */
        PyObject *kwargs = NULL;
        PyObject *callargs = fastcall_varargs(&st, &kwargs);

        if (callargs != NULL) {
            PyErr_Clear();
            (void)PyArg_ParseTupleAndKeywords(callargs, kwargs, "O|OO:iter_graphemes",
                                              keywords, &unistr, &start, &end);
            Py_DECREF(callargs);
            Py_XDECREF(kwargs);
        }
        return NULL;
    }
}

/*
 * clip(), bound for the gated fast path in wcwidth/_clip.py.
 *
 * Named py_clip_impl to avoid confusion with the file-static clip_impl() in libwcwidth/src/clip.c
 * (no link clash, but the collision reads badly).
 *
 * Unlike ljust()/rjust()/center(), this is NOT a drop-in for the Python clip(): libwcwidth's clip
 * is simplified and wcwidth/_clip.py calls when prerequisite conditions are met, 'start' and 'end'
 * arrive already normalized to non-negative column numbers.
 * 
 * Returns Py_RETURN_NONE to indicate "this is not supported in C11", for lone surrogates, and
 * complex terminal sequences like OSC 66 or cursor movement.
 */
static PyObject *
py_clip_impl(PyObject *module, PyObject *const *args, Py_ssize_t nargs, PyObject *kwnames)
{
    PyObject *text_obj = NULL;
    Py_ssize_t start = 0;
    Py_ssize_t end = -1;
    PyObject *fillchar_obj = NULL;
    int tabsize = 8;
    int ambiguous_width = 1;
    int propagate_sgr = 1;
    PyObject *control_codes_obj = NULL;
    PyObject *term_program_obj = NULL;
    static char *kwlist[] = {"text", "start", "end", "fillchar", "tabsize",
                             "ambiguous_width", "propagate_sgr", "control_codes",
                             "term_program", NULL};
    fastcall_stack st = {args, nargs, kwnames};
    Py_ssize_t i, nkw;

    (void)module;
    if (nargs > 3) {
        goto reject;
    }
    if (nargs > 0) {
        if (!PyUnicode_Check(args[0])) {
            goto reject;
        }
        text_obj = args[0];
    }
    if (nargs > 1 && py_long_as_ssize(args[1], &start) < 0) {
        goto reject;
    }
    if (nargs > 2 && py_long_as_ssize(args[2], &end) < 0) {
        goto reject;
    }
    nkw = kwnames == NULL ? 0 : PyTuple_Size(kwnames);
    for (i = 0; i < nkw; i++) {
        PyObject *value = args[nargs + i];
        switch (keyword_index(PyTuple_GetItem(kwnames, i), kwlist)) {
        case 0:  /* text */
            if (nargs > 0 || !PyUnicode_Check(value)) {
                goto reject;
            }
            text_obj = value;
            break;
        case 1:  /* start */
            if (py_long_as_ssize(value, &start) < 0) {
                goto reject;
            }
            break;
        case 2:  /* end */
            if (py_long_as_ssize(value, &end) < 0) {
                goto reject;
            }
            break;
        case 3:  /* fillchar */
            fillchar_obj = value;
            break;
        case 4:  /* tabsize */
            if (py_long_as_int(value, &tabsize) < 0) {
                goto reject;
            }
            break;
        case 5:  /* ambiguous_width */
            if (!convert_ambiguous_width(value, &ambiguous_width)) {
                goto reject;
            }
            break;
        case 6:  /* propagate_sgr */
            if (py_object_as_bool(value, &propagate_sgr) < 0) {
                goto reject;
            }
            break;
        case 7:  /* control_codes */
            control_codes_obj = value;
            break;
        case 8:  /* term_program */
            term_program_obj = value;
            break;
        default:
            goto reject;
        }
    }
    if (text_obj == NULL) {
        goto reject;
    }
    if (start < 0 || end < 0) {
        PyErr_SetString(PyExc_ValueError,
                        "clip() requires non-negative start and end; "
                        "normalize them in Python before calling");
        return NULL;
    }

    const char *term_program = term_program_cstr(term_program_obj, 0);
    if (term_program == NULL && PyErr_Occurred()) {
        return NULL;
    }
    int mode = control_codes_mode(control_codes_obj);
    if (mode < 0) {
        return NULL;
    }

    const char *text;
    Py_ssize_t text_len;
    if (unicode_to_utf8(text_obj, &text, &text_len) < 0) {
        /* unicode_to_utf8() clears only UnicodeEncodeError; anything else is
         * still live, and calling into Python with it set raises SystemError. */
        if (PyErr_Occurred()) {
            return NULL;
        }
        /* A lone surrogate has no UTF-8 form. */
        Py_RETURN_NONE;
    }
    const char *fillchar;
    size_t fillchar_len;
    if (fillchar_utf8(fillchar_obj, &fillchar, &fillchar_len) < 0) {
        if (PyErr_Occurred()) {
            return NULL;
        }
        Py_RETURN_NONE;
    }

    wcwidth_clip_opts_t opts = WCWIDTH_CLIP_OPTS_DEFAULT;
    opts.v_start = (size_t)start;
    /* clip_run() clamps both bounds to INT_MAX itself, so Python's
     * sys.maxsize sentinel for "to end of line" needs no special case. */
    opts.v_end = (size_t)end;
    opts.tabsize = tabsize;
    opts.ambiguous_width = ambiguous_width;
    opts.term_program = term_program;
    opts.propagate_sgr = propagate_sgr ? true : false;
    opts.fillchar = fillchar;
    opts.fillchar_len = fillchar_len;

    int error = WCWIDTH_ERROR_NONE;
    size_t out_len = 0;
    char *out = wcwidth_clip_u8(text, (size_t)text_len, (wcwidth_control_mode_t)mode,
                                &opts, &out_len, &error);
    if (out == NULL) {
        if (error == WCWIDTH_ERROR_UNSUPPORTED) {
            /* contains sequence libwcwidth does not support, E.g. OSC 66 or cursor movement. */
            Py_RETURN_NONE;
        }
        if (error != WCWIDTH_ERROR_NONE) {
            PyErr_SetString(PyExc_ValueError, width_error_message(error));
        } else {
            PyErr_NoMemory();
        }
        return NULL;
    }
    PyObject *result = PyUnicode_FromStringAndSize(out, (Py_ssize_t)out_len);
    free(out);
    return result;

reject:
    {
        /* Not a valid call: the parser below reports it. */
        PyObject *kwargs = NULL;
        PyObject *callargs = fastcall_varargs(&st, &kwargs);

        if (callargs != NULL) {
            PyErr_Clear();
            (void)PyArg_ParseTupleAndKeywords(callargs, kwargs, "U|nn$OiO&pOO", kwlist,
                                              &text_obj, &start, &end, &fillchar_obj,
                                              &tabsize, convert_ambiguous_width,
                                              &ambiguous_width, &propagate_sgr,
                                              &control_codes_obj, &term_program_obj);
            Py_DECREF(callargs);
            Py_XDECREF(kwargs);
        }
        return NULL;
    }
}

static PyMethodDef module_methods[] = {
    {"wcwidth", (PyCFunction)wcwidth_impl, METH_FASTCALL | METH_KEYWORDS,
     "wcwidth(wc, unicode_version='auto', ambiguous_width=1) -> int\n\n"
     "Return the printable width of a single Unicode character in terminal cells."},
    {"wcswidth", (PyCFunction)wcswidth_impl, METH_FASTCALL | METH_KEYWORDS,
     "wcswidth(pwcs, n=None, unicode_version='auto', ambiguous_width=1) -> int\n\n"
     "Return the printable width of a Unicode string in terminal cells."},
    {"wcstwidth", (PyCFunction)wcstwidth_impl, METH_FASTCALL | METH_KEYWORDS,
     "wcstwidth(pwcs, n=None, unicode_version='auto', ambiguous_width=1, term_program=True) -> int\n\n"
     "Return the printable width of a Unicode string on the terminal given by term_program."},
    {"width", (PyCFunction)width_impl, METH_FASTCALL | METH_KEYWORDS,
     "width(text, *, control_codes='parse', tabsize=8, ambiguous_width=1, term_program=False) -> int\n\n"
     "Return the maximum cursor extent of text containing control codes and sequences."},
    {"ljust", (PyCFunction)ljust_impl, METH_FASTCALL | METH_KEYWORDS,
     "ljust(text, dest_width, fillchar=' ', *, ...) -> str"},
    {"rjust", (PyCFunction)rjust_impl, METH_FASTCALL | METH_KEYWORDS,
     "rjust(text, dest_width, fillchar=' ', *, ...) -> str"},
    {"center", (PyCFunction)center_impl, METH_FASTCALL | METH_KEYWORDS,
     "center(text, dest_width, fillchar=' ', *, ...) -> str"},
    {"clip", (PyCFunction)py_clip_impl, METH_FASTCALL | METH_KEYWORDS,
     "clip(text, start, end, *, ...) -> str | None\n\n"
     "Clip text to a visible column range, or None when the input has no UTF-8\n"
     "form.  Simplified relative to Python's clip(); start and end must already\n"
     "be non-negative.  Call only through wcwidth._clip.clip(), which gates on\n"
     "the subset where the two agree."},
    {"strip_sequences", (PyCFunction)strip_sequences_impl, METH_FASTCALL | METH_KEYWORDS,
     "strip_sequences(text) -> str\n\n"
     "Return text with all terminal escape sequences removed."},
    {"propagate_sgr", (PyCFunction)propagate_sgr_impl, METH_FASTCALL | METH_KEYWORDS,
     "propagate_sgr(lines) -> list[str]\n\n"
     "Propagate SGR styles across a list of lines."},
    {"iter_graphemes", (PyCFunction)iter_graphemes_impl, METH_FASTCALL | METH_KEYWORDS,
     "iter_graphemes(unistr, start=0, end=None) -> Iterator[str]\n\n"
     "Iterate over grapheme clusters by UAX #29 extended grapheme cluster rules."},
    {NULL, NULL, 0, NULL},
};

/*
 * Multi-phase initialisation (PEP 489), so the module can declare that it
 * does not need the GIL (PEP 703).
 *
 * On a free-threaded build, importing a module that has not declared
 * Py_MOD_GIL_NOT_USED re-enables the GIL for the whole process -- so a
 * single-phase module here would serialise every thread in an application
 * that merely measures string widths.  Declaring it is safe because
 * libwcwidth has no mutable global state: every table is `const`, the
 * functions take all their inputs as arguments, and this wrapper never
 * caches anything between calls.  The GIL is also never released, so the
 * borrowed CPython buffers used below stay valid.
 *
 * m_size is the size of the per-interpreter state below, which holds the one
 * heap type this module defines.  Per-interpreter (rather than static) state
 * is what makes the module safe under subinterpreters.
 */

static int
module_exec(PyObject *module)
{
    module_state *state = (module_state *)PyModule_GetState(module);
    PyObject *type = PyType_FromModuleAndSpec(module, &grapheme_iterator_spec, NULL);

    if (type == NULL) {
        return -1;
    }
    /* deliberately not added to the module dict: the type is an implementation
     * detail, only reachable by iterating */
    state->grapheme_iterator_type = (PyTypeObject *)type;
    return 0;
}

static int
module_traverse(PyObject *module, visitproc visit, void *arg)
{
    module_state *state = (module_state *)PyModule_GetState(module);

    if (state != NULL) {
        Py_VISIT(state->grapheme_iterator_type);
    }
    return 0;
}

static int
module_clear(PyObject *module)
{
    module_state *state = (module_state *)PyModule_GetState(module);

    if (state != NULL) {
        Py_CLEAR(state->grapheme_iterator_type);
    }
    return 0;
}

static void
module_free(void *module)
{
    (void)module_clear((PyObject *)module);
}

/* Slot value constants follow the limited API version that added them, so
 * compare against Py_LIMITED_API when it is set.  From 3.15 Py_mod_gil is
 * defined for every build, so the GIL slot is gated on its value constant. */
#ifdef Py_LIMITED_API
#  define WCWIDTH_API_LEVEL Py_LIMITED_API
#else
#  define WCWIDTH_API_LEVEL PY_VERSION_HEX
#endif

static PyModuleDef_Slot module_slots[] = {
    {Py_mod_exec, (void *)module_exec},
#if WCWIDTH_API_LEVEL >= 0x030C0000
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
#endif
#if defined(Py_mod_gil) && defined(Py_MOD_GIL_NOT_USED)
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL},
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    "_wcwidth_c",
    "Optional CPython wrapper around the portable C11 libwcwidth library.",
    sizeof(module_state),
    module_methods,
    module_slots,
    module_traverse,
    module_clear,
    module_free,
};

PyMODINIT_FUNC
PyInit__wcwidth_c(void)
{
    return PyModuleDef_Init(&module_def);
}
