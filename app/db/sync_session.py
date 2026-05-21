from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from sqlalchemy.pool import NullPool, QueuePool


# Determine if we need SSL(Neon/Supabase needs SSL), local DB doesn't need it
is_local = settings.APP_ENV == "development"


sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    echo=False,
    future=True,
    poolclass=QueuePool if is_local else NullPool,  # Essential for NEON DB
)


SyncSessionLocal = sessionmaker(
    sync_engine,
    expire_on_commit=False,
    autoflush=False,  # pending changes are not sent to db. intentional: sync session is for middleware/audit use only
    # doesn't commit to db without calling session.commit()/db.commit() , default False
    autocommit=False
)


def get_sync_db_session():
    with SyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
