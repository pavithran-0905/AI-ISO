"""Alembic migration environment.

Resolves this service's own DSN from :func:`app.config.settings
.get_settings` (never hardcoded in ``alembic.ini``), converted to the
sync ``psycopg`` DSN Alembic's command API needs via
:func:`shared_core.database.migration.sync_dsn`, and targets
``app.models``' full :data:`~shared_core.database.base.Base.metadata`
for autogenerate support.

**Uses a service-scoped ``version_table``.** Every AI-IOS service
connects to the same physical ``aiios`` Postgres database (there is one
shared instance, not one per service), so Alembic's default single
``alembic_version`` table cannot record more than one service's
migration chain at a time -- the second service to run ``upgrade head``
would fail with "Can't locate revision" against a revision id from a
different service's history entirely. Naming this service's version
table ``alembic_version_observability_platform_service`` gives it an
independent history row, the same way every other table this service
owns is already namespaced by being defined only in ``app.models``.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from shared_core.database.base import Base
from shared_core.database.migration import sync_dsn
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  -- import registers every table with Base.metadata
from app.config.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", sync_dsn(get_settings().database.dsn))

target_metadata = Base.metadata

VERSION_TABLE = "alembic_version_observability_platform_service"


def run_migrations_offline() -> None:
    """Emit migration SQL without a live database connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, version_table=VERSION_TABLE
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
