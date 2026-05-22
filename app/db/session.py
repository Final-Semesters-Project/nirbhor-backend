from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

# Determine if we need SSL(Neon/Supabase needs SSL), local DB doesn't need it
is_local = settings.APP_ENV == "development"

# pgBouncer (NeonDB) in transaction mode doesn't support prepared statements
# local Postgres doesn't need these restrictions
if is_local:
    connect_args = {}
else:
    # Add SSL if not in local
    connect_args = {
        "ssl": True,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }


# create async engine for database session
engine = create_async_engine(
    settings.DATABASE_URL,
    # NullPool for NEON DB because it uses pgbouncer for connection pooling and
    # AsyncAdaptedQueuePool(which is default) for local DB
    poolclass=NullPool if not is_local else AsyncAdaptedQueuePool,
    connect_args=connect_args,
    future=True,  # this enables sqlalchemy 2.0
    echo=False  # disable sqlalchemy logging, we will use loguru instead
)


# create async session
AsyncSessionLocal = async_sessionmaker(
    engine,
    # don't expire objects after commit (avoids lazy load errors in async)
    expire_on_commit=False,
    autocommit=False
)
# Note on expire_on_commit: With expire_on_commit=True (default), after await db.commit(), SQLAlchemy marks all loaded objects as "expired". Accessing any attribute then triggers a lazy load — but in async SQLAlchemy, lazy loading raises an error because there's no implicit async context to run the query. expire_on_commit=False prevents this, so you can safely access new_user.id after committing without triggering another DB query.


# Dependency for database session
async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
