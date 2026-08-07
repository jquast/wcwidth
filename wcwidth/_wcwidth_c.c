/*
 * CPython extension wrapping libwcwidth.
 *
 * Optional module: when this module cannot be imported, wcwidth/__init__.py
 * falls back to the Python implementation.
 *
 * Design notes:
 *   - Width measurement functions (wcwidth, wcswidth, width) operate on
 *     uint32_t codepoints via PyUnicode_READ, which is zero-copy for
 *     4-byte-kind strings and matches the C library's native _u32 API.
 *   - Byte-oriented functions (wrap, clip, align, strip_sequences,
 *     propagate_sgr) encode via PyUnicode_AsUTF8AndSize.
 *   - Inputs the C library cannot represent faithfully are dispatched to the
 *     Python implementation at call time.  Exactly one remains:
 *       * lone surrogates -- UTF-8 cannot encode them, and the byte-oriented
 *         C functions have no _u32 variants.
 *   - Terminal override tables (term_program) are applied by the C library
 *     itself; the wrapper only resolves the Python term_program value to an
 *     identifier string (see term_program_cstr).
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "wcwidth/wcwidth.h"
#include "wcwidth/width.h"
#include "wcwidth/align.h"
#include "wcwidth/escape.h"
#include "wcwidth/sgr.h"

static const uint32_t *
unicode_codepoints(PyObject *text, Py_ssize_t *count, uint32_t **heap_buf)
{
    Py_ssize_t len = PyUnicode_GET_LENGTH(text);
    int kind = PyUnicode_KIND(text);

    if (kind == PyUnicode_4BYTE_KIND) {
        *heap_buf = NULL;
        *count = len;
        return (const uint32_t *)PyUnicode_DATA(text);
    }

    uint32_t *buf = PyMem_Malloc((size_t)len * sizeof(uint32_t));
    if (buf == NULL) {
        PyErr_NoMemory();
        return NULL;
    }
    const void *data = PyUnicode_DATA(text);
    for (Py_ssize_t i = 0; i < len; i++) {
        buf[i] = PyUnicode_READ(kind, data, i);
    }
    *heap_buf = buf;
    *count = len;
    return buf;
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

static PyObject *
call_python_function(const char *module_name, const char *function_name,
                   PyObject *args, PyObject *kwargs)
{
    PyObject *module = PyImport_ImportModule(module_name);
    if (module == NULL) {
        return NULL;
    }
    PyObject *function = PyObject_GetAttrString(module, function_name);
    Py_DECREF(module);
    if (function == NULL) {
        return NULL;
    }
    PyObject *result = PyObject_Call(function, args, kwargs);
    Py_DECREF(function);
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
    const char *value = PyUnicode_AsUTF8(obj);
    if (value == NULL) {
        return -1;
    }
    if (strcmp(value, "ignore") == 0) {
        return WCWIDTH_IGNORE;
    }
    if (strcmp(value, "strict") == 0) {
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
    if (fillchar_obj == NULL || fillchar_obj == Py_None) {
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

static const char *
option_utf8(PyObject *obj, const char *name, const char *default_value)
{
    if (obj == NULL) {
        return default_value;
    }
    if (!PyUnicode_Check(obj)) {
        PyErr_Format(PyExc_TypeError, "%s must be a string", name);
        return NULL;
    }
    return PyUnicode_AsUTF8(obj);
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
        if (PyUnicode_GET_LENGTH(obj) == 0) {
            return NULL;
        }
        return PyUnicode_AsUTF8(obj);
    }
    PyErr_Format(PyExc_AttributeError,
                 "'%s' object has no attribute 'strip'", Py_TYPE(obj)->tp_name);
    return NULL;
}

static PyObject *
wcwidth_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *wc_obj;
    PyObject *dummy_unicode_version = NULL;
    int ambiguous_width = 1;
    static char *kwlist[] = {"wc", "unicode_version", "ambiguous_width", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|Oi", kwlist,
                                     &wc_obj, &dummy_unicode_version, &ambiguous_width)) {
        return NULL;
    }

    int truthy = PyObject_IsTrue(wc_obj);
    if (truthy < 0) {
        return NULL;
    }
    uint32_t ucs = 0;
    if (truthy) {
        if (!PyUnicode_Check(wc_obj)) {
            PyErr_Format(PyExc_TypeError,
                         "ord() expected a character, but object of type '%s' found",
                         Py_TYPE(wc_obj)->tp_name);
            return NULL;
        }
        Py_ssize_t char_count = PyUnicode_GET_LENGTH(wc_obj);
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
}

static PyObject *
wcswidth_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *pwcs_obj;
    PyObject *n_obj = NULL;
    PyObject *dummy_unicode_version = NULL;
    int ambiguous_width = 1;
    static char *kwlist[] = {"pwcs", "n", "unicode_version", "ambiguous_width", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "U|OOi", kwlist,
                                     &pwcs_obj, &n_obj, &dummy_unicode_version,
                                     &ambiguous_width)) {
        return NULL;
    }

    uint32_t *heap_buf = NULL;
    Py_ssize_t len;
    const uint32_t *codepoints = unicode_codepoints(pwcs_obj, &len, &heap_buf);
    if (codepoints == NULL) {
        return NULL;
    }

    Py_ssize_t count = resolve_count(n_obj, len);
    if (count < 0) {
        PyMem_Free(heap_buf);
        return NULL;
    }

    int result = wcswidth_u32(codepoints, (size_t)count, ambiguous_width);
    PyMem_Free(heap_buf);
    return PyLong_FromLong(result);
}

static PyObject *
wcstwidth_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *pwcs_obj;
    PyObject *n_obj = NULL;
    PyObject *dummy_unicode_version = NULL;
    int ambiguous_width = 1;
    PyObject *term_program_obj = NULL;
    static char *kwlist[] = {"pwcs", "n", "unicode_version", "ambiguous_width",
                             "term_program", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "U|OOiO", kwlist,
                                     &pwcs_obj, &n_obj, &dummy_unicode_version,
                                     &ambiguous_width, &term_program_obj)) {
        return NULL;
    }

    const char *term_program = term_program_cstr(term_program_obj, 1);
    if (term_program == NULL && PyErr_Occurred()) {
        return NULL;
    }

    uint32_t *heap_buf = NULL;
    Py_ssize_t len;
    const uint32_t *codepoints = unicode_codepoints(pwcs_obj, &len, &heap_buf);
    if (codepoints == NULL) {
        return NULL;
    }

    Py_ssize_t count = resolve_count(n_obj, len);
    if (count < 0) {
        PyMem_Free(heap_buf);
        return NULL;
    }

    int result = wcstwidth_u32(codepoints, (size_t)count, ambiguous_width, term_program);
    PyMem_Free(heap_buf);
    return PyLong_FromLong(result);
}

static PyObject *
width_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *text_obj;
    PyObject *control_codes_obj = NULL;
    int tabsize = 8;
    int ambiguous_width = 1;
    PyObject *term_program_obj = NULL;
    static char *kwlist[] = {"text", "control_codes", "tabsize", "ambiguous_width",
                             "term_program", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "U|OiiO", kwlist,
                                     &text_obj, &control_codes_obj, &tabsize,
                                     &ambiguous_width, &term_program_obj)) {
        return NULL;
    }
    if (PyTuple_GET_SIZE(args) > 1) {
        PyErr_Format(PyExc_TypeError,
                     "width() takes 1 positional argument but %zd were given",
                     PyTuple_GET_SIZE(args));
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
    /* 'strict' mode routes to the Python implementation: the C library cannot
     * reproduce the ValueError messages for invalid text-sizing parameters,
     * which embed the offending value. */
    if (mode == WCWIDTH_STRICT) {
        return call_python_function("wcwidth._width", "width", args, kwargs);
    }

    uint32_t *heap_buf = NULL;
    Py_ssize_t len;
    const uint32_t *codepoints = unicode_codepoints(text_obj, &len, &heap_buf);
    if (codepoints == NULL) {
        return NULL;
    }

    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;
    opts.tabsize = tabsize;
    opts.ambiguous_width = ambiguous_width;
    opts.term_program = term_program;

    int error = 0;
    int result = width_u32(codepoints, (size_t)len, (wcwidth_control_mode_t)mode, &opts, &error);
    PyMem_Free(heap_buf);

    if (error) {
        PyErr_SetString(PyExc_ValueError, width_error_message(error));
        return NULL;
    }
    return PyLong_FromLong(result);
}

static PyObject *
align_impl(const char *name, PyObject *args, PyObject *kwargs)
{
    PyObject *text_obj;
    Py_ssize_t dest_width;
    PyObject *fillchar_obj = NULL;
    PyObject *control_codes_obj = NULL;
    int ambiguous_width = 1;
    PyObject *term_program_obj = NULL;
    static char *kwlist[] = {"text", "dest_width", "fillchar", "control_codes",
                             "ambiguous_width", "term_program", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Un|OOiO", kwlist,
                                     &text_obj, &dest_width, &fillchar_obj,
                                     &control_codes_obj, &ambiguous_width,
                                     &term_program_obj)) {
        return NULL;
    }
    if (PyTuple_GET_SIZE(args) > 3) {
        PyErr_Format(PyExc_TypeError,
                     "%s() takes 3 positional arguments but %zd were given",
                     name, PyTuple_GET_SIZE(args));
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

    size_t padded_width = dest_width > 0 ? (size_t)dest_width : 0;

    const char *text;
    Py_ssize_t text_len;
    if (unicode_to_utf8(text_obj, &text, &text_len) < 0) {
        return call_python_function("wcwidth.align", name, args, kwargs);
    }
    const char *fillchar;
    size_t fillchar_len;
    if (fillchar_utf8(fillchar_obj, &fillchar, &fillchar_len) < 0) {
        if (PyErr_Occurred()) {
            return NULL;
        }
        return call_python_function("wcwidth.align", name, args, kwargs);
    }

    int error = WCWIDTH_ERROR_NONE;
    size_t out_len = 0;
    char *out;
    if (strcmp(name, "ljust") == 0) {
        out = ljust_u8(text, (size_t)text_len, padded_width, fillchar, fillchar_len,
                       (wcwidth_control_mode_t)mode, ambiguous_width, term_program, &out_len, &error);
    } else if (strcmp(name, "rjust") == 0) {
        out = rjust_u8(text, (size_t)text_len, padded_width, fillchar, fillchar_len,
                       (wcwidth_control_mode_t)mode, ambiguous_width, term_program, &out_len, &error);
    } else {
        out = center_u8(text, (size_t)text_len, padded_width, fillchar, fillchar_len,
                        (wcwidth_control_mode_t)mode, ambiguous_width, term_program, &out_len, &error);
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
}

static PyObject *
ljust_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    return align_impl("ljust", args, kwargs);
}

static PyObject *
rjust_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    return align_impl("rjust", args, kwargs);
}

static PyObject *
center_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    return align_impl("center", args, kwargs);
}

static PyObject *
strip_sequences_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *text_obj;
    static char *kwlist[] = {"text", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "U", kwlist, &text_obj)) {
        return NULL;
    }

    const char *text;
    Py_ssize_t text_len;
    if (unicode_to_utf8(text_obj, &text, &text_len) < 0) {
        return call_python_function("wcwidth.escape_sequences", "strip_sequences", args, kwargs);
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
}

static PyObject *
propagate_sgr_impl(PyObject *self, PyObject *args, PyObject *kwargs)
{
    PyObject *lines_obj;
    static char *kwlist[] = {"lines", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwlist, &lines_obj)) {
        return NULL;
    }

    PyObject *fast = PySequence_Fast(lines_obj, "lines must be an iterable of strings");
    if (fast == NULL) {
        return NULL;
    }
    Py_ssize_t nlines = PySequence_Fast_GET_SIZE(fast);
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
    Py_ssize_t i;
    for (i = 0; i < nlines; i++) {
        PyObject *line = PySequence_Fast_GET_ITEM(fast, i);
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
            return call_python_function("wcwidth.sgr_state", "propagate_sgr", args, kwargs);
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
        result = call_python_function("wcwidth.sgr_state", "propagate_sgr", args, kwargs);
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
                PyList_SET_ITEM(result, i, line);
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
}

static PyMethodDef module_methods[] = {
    {"wcwidth", (PyCFunction)wcwidth_impl, METH_VARARGS | METH_KEYWORDS,
     "wcwidth(wc, unicode_version='auto', ambiguous_width=1) -> int\n\n"
     "Return the printable width of a single Unicode character in terminal cells."},
    {"wcswidth", (PyCFunction)wcswidth_impl, METH_VARARGS | METH_KEYWORDS,
     "wcswidth(pwcs, n=None, unicode_version='auto', ambiguous_width=1) -> int\n\n"
     "Return the printable width of a Unicode string in terminal cells."},
    {"wcstwidth", (PyCFunction)wcstwidth_impl, METH_VARARGS | METH_KEYWORDS,
     "wcstwidth(pwcs, n=None, unicode_version='auto', ambiguous_width=1, term_program=True) -> int\n\n"
     "Return the printable width of a Unicode string on the terminal given by term_program."},
    {"width", (PyCFunction)width_impl, METH_VARARGS | METH_KEYWORDS,
     "width(text, *, control_codes='parse', tabsize=8, ambiguous_width=1, term_program=False) -> int\n\n"
     "Return the maximum cursor extent of text containing control codes and sequences."},
    {"ljust", (PyCFunction)ljust_impl, METH_VARARGS | METH_KEYWORDS,
     "ljust(text, dest_width, fillchar=' ', *, ...) -> str"},
    {"rjust", (PyCFunction)rjust_impl, METH_VARARGS | METH_KEYWORDS,
     "rjust(text, dest_width, fillchar=' ', *, ...) -> str"},
    {"center", (PyCFunction)center_impl, METH_VARARGS | METH_KEYWORDS,
     "center(text, dest_width, fillchar=' ', *, ...) -> str"},
    {"strip_sequences", (PyCFunction)strip_sequences_impl, METH_VARARGS | METH_KEYWORDS,
     "strip_sequences(text) -> str\n\n"
     "Return text with all terminal escape sequences removed."},
    {"propagate_sgr", (PyCFunction)propagate_sgr_impl, METH_VARARGS | METH_KEYWORDS,
     "propagate_sgr(lines) -> list[str]\n\n"
     "Propagate SGR styles across a list of lines."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    "_wcwidth_c",
    "Optional CPython wrapper around the portable C11 libwcwidth library.",
    -1,
    module_methods,
};

PyMODINIT_FUNC
PyInit__wcwidth_c(void)
{
    return PyModule_Create(&module_def);
}
