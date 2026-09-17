"""Process-level memoization for immutable scheme load results.

Worker threads re-run scheme loading once per sample: allele FASTA
parsing, exact-hash index JSON parsing, and ST profile TSV parsing are
pure read+parse operations whose results are immutable after build, so
they are memoized per process. Memo keys embed file identity
(``st_mtime_ns`` and ``st_size``), so any rewrite — scheme updates,
``force_reindex`` rebuilds, test fixtures — changes the key and forces a
fresh load; stale-cache behavior is impossible by construction.

Thread safety: CPython dict/OrderedDict reads and single-key assignment
are atomic, and memoized values are never mutated after insertion, so no
lock is required.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable

_MAX_MEMO_ENTRIES = 4

_MEMOS: dict[str, object] = {}


def register_memo(name: str, memo: object) -> None:
    """Register *memo* so :func:`clear_scheme_load_memos` can drop it."""
    _MEMOS[name] = memo


def memoized[K: Hashable, V](
    memo: OrderedDict[K, V], key: K, build: Callable[[], V]
) -> V:
    """Return ``memo[key]``, building it and evicting past N entries."""
    if key in memo:
        memo.move_to_end(key)
        return memo[key]
    value = build()
    memo_store(memo, key, value)
    return value


def memo_store[K: Hashable, V](memo: OrderedDict[K, V], key: K, value: V) -> None:
    """Insert *value* and evict oldest entries beyond N."""
    memo[key] = value
    while len(memo) > _MAX_MEMO_ENTRIES:
        memo.popitem(last=False)


def clear_scheme_load_memos() -> None:
    """Drop every registered scheme load memo (test isolation)."""
    for memo in _MEMOS.values():
        if isinstance(memo, dict):
            memo.clear()
