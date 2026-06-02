"""
Lazy-loading per-terminal grapheme override tables.

This minimizes memory for the 99.9% of use-cases of a single 'term_program'.
"""
from __future__ import annotations

# std imports
import importlib
from functools import lru_cache

# local
from ._registry import _REGISTRY


@lru_cache(maxsize=32)
def get(term_canonical: str | None) -> dict[str, int] | None:
    """
    Return grapheme override dict for a terminal, or None.

    The per-terminal module is imported on first access and cached in ``sys.modules``; subsequent
    calls for the same terminal return immediately via lru_cache.
    """
    if term_canonical is None:
        return None
    hash_key = _REGISTRY.get(term_canonical)
    if hash_key is None:
        return None

    try:
        mod = importlib.import_module(f'._known_{hash_key}', __package__)
        result: dict[str, int] = getattr(mod, 'GRAPHEMES')
        return result
    except ImportError:
        # This can occur during a program re-install when the registry and files are out of sync
        # (filesystem vs. in-memory copy differ due to upgrade).
        return None
