"""Tests for clear error on multi-character wcwidth() input."""

# 3rd party
import pytest

# local
from wcwidth import wcwidth


def test_wcwidth_multichar_raises_clear():
    with pytest.raises(TypeError, match='single character'):
        wcwidth('ab')
    assert wcwidth('a') == 1
    assert wcwidth(b'a') == 1     # backward-compat preserved
    assert wcwidth(None) == 0
