from alembic import context

from database import Base, create_database_engine, get_database_url
import income_models  # Register the mapped tables with Base.metadata.
import bill_models
import account_models


config = context.config
target_metadata = Base.metadata
database_url = config.attributes.get("database_url")

if context.is_offline_mode():
    context.configure(
        url=get_database_url(database_url), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_database_engine(database_url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
