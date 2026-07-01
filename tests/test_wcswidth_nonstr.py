"""Tests for clear TypeError on non-string wcswidth() input."""

# 3rd party
import pytest

# local
from wcwidth import wcswidth


def test_wcswidth_nonstr_raises_clear():
    with pytest.raises(TypeError, match='wcswidth\\(\\) expects a string'):
        wcswidth(123)
    assert wcswidth('hello') == 5
    assert wcswidth('') == 0
