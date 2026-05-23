from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
import os
from alembic import context
from dotenv import load_dotenv
from geoalchemy2 import alembic_helpers
from app.db.base import Base
from app.models import User, ProviderProfile, Category, Skill, ProviderSkillLink, FCMToken, Booking, Team, UrgentBroadcast, UserSession, UserReport

# import models from app.models to here manually if alembic doesn't generate them

# if not sync_database_url:
#     raise ValueError("SYNC_DATABASE_URL is not set in your .env file!")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


# This function is added so that alembic doesn't delete the tables that are not part of Base.metadata like table from default PostGIS extension
def include_object(object, name, type_, reflected, compare_to):
    # Only include tables that are part of your Base.metadata
    if type_ == "table" and name not in target_metadata.tables:
        return False
    # Explicitly ignore sequences owned by PostGIS/Tiger
    if type_ == "sequence" and reflected and object.info.get("skip_autogenerate", False):
        return False
    return True

# TODO: add geometry types to columns when starting to use PostGIS in provider_profile and others. We need to configure alembic for this(Alembic is showing warnings in the console for not having geometry types)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        # ↓ GeoAlchemy2's built-in render function — handles Geometry correctly
        render_item=alembic_helpers.render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 1 and 2 are added manually to solve alembic migration error
    load_dotenv()

    # 1. Get the URL from your environment variable
    sync_database_url = os.getenv("SYNC_DATABASE_URL")

    if not sync_database_url:
        raise ValueError("SYNC_DATABASE_URL is not set in your .env file!")

    # 2. Force it into the config object so engine_from_config can find it
    config.set_main_option("sqlalchemy.url", sync_database_url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            include_object=include_object,
            # ↓ GeoAlchemy2's built-in render function — handles Geometry correctly
            render_item=alembic_helpers.render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
