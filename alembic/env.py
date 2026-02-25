import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# Load .env
load_dotenv()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ Import Base + models so metadata is populated
from app.db.session import Base
from app import models  # imports app/models/__init__.py

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = os.getenv("DATABASE_URL_SYNC")
    if not url:
        raise RuntimeError("Missing DATABASE_URL_SYNC in .env")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = os.getenv("DATABASE_URL_SYNC")
    if not url:
        raise RuntimeError("Missing DATABASE_URL_SYNC in .env")

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()