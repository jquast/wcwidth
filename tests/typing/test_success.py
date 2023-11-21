import sys
import wcwidth
from typing import Tuple


if sys.version_info >= (3,):
    unicode = str


def test_list_versions():  # type: () -> None
    versions = wcwidth.list_versions()  # type: Tuple[str, ...]
    assert isinstance(versions, tuple)
    for version in versions:
        assert isinstance(version, str)


def test_wcwidth():  # type: () -> None
    width = wcwidth.wcwidth("a")  # type: int
    assert isinstance(width, int)
    width = wcwidth.wcwidth(u"啊")
    assert isinstance(width, int)

    width = wcwidth.wcwidth("b", "9.0")
    assert isinstance(width, int)
    width = wcwidth.wcwidth("b", u"9.0")
    assert isinstance(width, int)


def test_wcswidth():  # type: () -> None
    width = wcwidth.wcswidth("hello, world")  # type: int
    assert isinstance(width, int)
    width = wcwidth.wcswidth(u"你好，世界")
    assert isinstance(width, int)

    width = wcwidth.wcswidth(u"你好，世界", 5)
    assert isinstance(width, int)

    width = wcwidth.wcswidth("hello, world", unicode_version="9.0")
    assert isinstance(width, int)
    width = wcwidth.wcswidth("hello, world", unicode_version=u"9.0")
    assert isinstance(width, int)

    width = wcwidth.wcswidth(u"你好，世界", 5, "9.0")
    assert isinstance(width, int)


def test__bisearch():  # type: () -> None
    found = wcwidth._bisearch(6, [(1, 2), (4, 7)])  # type: int
    assert isinstance(found, int)


def test__wcversion_value():  # type: () -> None
    version = wcwidth._wcversion_value("12.1.0")  # type: Tuple[int, ...]
    assert isinstance(version, tuple)
    for number in version:
        assert isinstance(number, int)


def test__wcmatch_version():  # type: () -> None
    version_str = wcwidth._wcmatch_version("auto")  # type: str
    assert isinstance(version_str, str)
    version_unicode = wcwidth._wcmatch_version(u"auto")  # type: unicode
    assert isinstance(version_unicode, unicode)
