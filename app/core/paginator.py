from math import ceil
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.pagination_schema import PageResponse


async def paginate(
    db: AsyncSession,
    stmt,           # your existing SELECT statement — no changes needed
    # The primary key column for counting (e.g. Booking.id). Used to build a clean COUNT subquery that strips. ORM options like selectinload which break COUNT(*)
    pk_col,
    page: int,
    page_size: int,
    transformer=None,   # optional: function to transform each row
) -> PageResponse:
    """
    Generic offset paginator for any SQLAlchemy SELECT statement.

    IMPORTANT: Pass a Select object, not an awaited result or coroutine.
    Correct:   paginate(db, booking_repo.get_history_stmt(id), Booking.id, ...)
    Wrong:     paginate(db, await booking_repo.get_history(id), ...)

    COUNT strategy:
        We use stmt.with_only_columns(pk_col).subquery() for counting.
        This strips selectinload and other ORM options that would cause
        COUNT(*) to fail or return wrong results on joined queries.
        Result: SELECT COUNT(*) FROM (SELECT booking.id FROM ... WHERE ...) AS subq
        This is always correct regardless of joins or eager loading options.

    LIMIT/OFFSET:
        Applied to the original stmt unchanged.
        selectinload fires as a second query per SQLAlchemy's design —
        it is NOT part of the SQL LIMIT/OFFSET, so it correctly loads
        only the relationships for the paginated rows.
    """
    # Clamp page to valid range
    page = max(1, page)
    page_size = max(1, min(page_size, 100))  # hard cap at 100
    offset = (page - 1) * page_size

    # COUNT: strip to just the pk column to avoid issues with selectinload,
    # GROUP BY, DISTINCT or multi-column selects from joins
    count_subq = stmt.with_only_columns(pk_col).subquery()
    total = await db.scalar(select(func.count()).select_from(count_subq)) or 0

    # Fetch the actual page — selectinload fires here as a second internal query
    page_stmt = stmt.limit(page_size).offset(offset)
    result = await db.execute(page_stmt)

    # Handle both:
    # - Single-model queries (select(Booking)) → use scalars()
    # - Multi-column/join queries (select(Booking, User)) → use all() for tuples
    if stmt.is_select:
        cols = stmt.selected_columns
        # If more than one entity/column selected, result is tuples
        use_tuples = len(list(cols)) > 1
    else:
        use_tuples = False

    rows = result.all() if use_tuples else result.scalars().all()

    items = [transformer(row) for row in rows] if transformer else list(rows)
    total_pages = ceil(total / page_size) if total > 0 else 1

    return PageResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
