"""
Lazy-loading per-terminal grapheme override tables.

This minimizes memory for the 99.9% of use-cases of a single 'term_program'.
"""
from __future__ import annotations

import importlib
from functools import lru_cache


@lru_cache(maxsize=32)
def get(term_canonical: str | None) -> dict[str, int] | None:
    """
    Return grapheme override dict for a terminal, or None.

    The per-terminal module is imported on first access and cached in ``sys.modules``; subsequent
    calls for the same terminal return immediately via lru_cache.
    """
    if term_canonical is None:
        return None
    safe_name = term_canonical.replace('-', '_').replace('.', '_')
    if not safe_name.isidentifier() or safe_name.startswith('_'):
        return None
    try:
        mod = importlib.import_module(f'.{safe_name}', __package__)
        result: dict[str, int] = getattr(mod, 'GRAPHEMES')
        return result
    except ImportError:
        return None
