"""Shared helper for column-allowlisted SQLAlchemy sorting.

Every list endpoint that supports ``?sort_by=…&sort_dir=asc|desc`` runs the
caller's input through ``apply_sort`` with a per-endpoint allowlist mapping
user-facing keys to SQLAlchemy columns / expressions. Anything not in the
allowlist falls back silently to the endpoint's default column + direction,
which both prevents SQL injection via arbitrary column names and gives the
endpoint a stable canonical order when the frontend doesn't pass a sort.

Nulls are pushed to the end of the result in both directions so the user
never sees a wall of "—" rows above their data when sorting by a column
like ``submitted_at`` that legitimately has missing values.
"""
from typing import Any, Mapping, Optional

from sqlalchemy import asc, desc


def _order_expr(col: Any, direction: str):
    expr = asc(col) if direction == "asc" else desc(col)
    # ``nullslast()`` is supported by both Postgres and SQLite via SQLAlchemy's
    # nulls-as-clause translation; guard for older dialects defensively.
    try:
        expr = expr.nullslast()
    except AttributeError:
        pass
    return expr


def apply_sort(
    query,
    *,
    sort_by: Optional[str],
    sort_dir: Optional[str],
    allowed: Mapping[str, Any],
    default_col: Any,
    default_dir: str = "desc",
    tiebreaker: Optional[Any] = None,
):
    """Apply ``ORDER BY`` to ``query`` from user input.

    Args:
        query: SQLAlchemy query (or select).
        sort_by: User-supplied column key. Must be a key of ``allowed`` to be
            honoured; unknown keys fall back to ``default_col`` silently.
        sort_dir: ``"asc"`` or ``"desc"``. Anything else falls back to
            ``default_dir``.
        allowed: Mapping of user-facing key -> SQLAlchemy column / expression.
        default_col: Column used when ``sort_by`` is missing or rejected.
        default_dir: Direction used when ``sort_by`` is missing or rejected,
            *or* when sort_dir is missing / invalid.
        tiebreaker: Optional column to append as a secondary, always-desc
            sort so pagination is deterministic when the primary key has
            ties (e.g. lots of rows with the same ``status``).

    Returns the query with ``order_by(…)`` applied.
    """
    col = allowed.get(sort_by) if sort_by else None
    direction = (sort_dir or "").lower()
    if col is None:
        # Unknown / missing sort_by -> canonical default.
        col = default_col
        direction = default_dir
    elif direction not in ("asc", "desc"):
        # Known column but invalid direction -> use default direction.
        direction = default_dir

    query = query.order_by(_order_expr(col, direction))
    if tiebreaker is not None and tiebreaker is not col:
        query = query.order_by(_order_expr(tiebreaker, "desc"))
    return query
