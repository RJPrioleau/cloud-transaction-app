"""Explicit database setup; importing this module never creates a database."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session


PROJECT_ROOT = Path(__file__).resolve().parent


class Base(DeclarativeBase):
    pass


def get_database_url(database_url=None):
    configured = database_url or os.environ.get("DATABASE_URL")
    if not configured:
        configured = "sqlite:///instance/development.sqlite3"
    url = make_url(configured)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        path = Path(url.database)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        url = url.set(database=str(path.resolve()))
    return url


def create_database_engine(database_url=None):
    url = get_database_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, connection_record):
            cursor = connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()
    return engine


@contextmanager
def session_scope(engine):
    """Commit the complete operation, or roll it all back on failure."""
    with Session(engine, expire_on_commit=False) as session:
        with session.begin():
            yield session


def backup_sqlite_database(engine, destination):
    """Create a consistent local SQLite backup without replacing an existing file.

    This is a development tool, not the future PostgreSQL recovery strategy.
    Call it outside an active write transaction.
    """
    if engine.dialect.name != "sqlite" or engine.url.database in (None, "", ":memory:"):
        raise ValueError("Backup requires a file-based SQLite database.")
    source = Path(engine.url.database).resolve()
    destination = Path(destination).resolve()
    if destination == source or destination.exists():
        raise FileExistsError("Choose a new backup file; existing files are never replaced.")
    if not source.is_file():
        raise FileNotFoundError("Source database does not exist.")
    source_connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    try:
        # Reserve this name atomically so simultaneous backups cannot overwrite it.
        with destination.open("xb"):
            pass
        try:
            destination_connection = sqlite3.connect(str(destination))
            try:
                source_connection.backup(destination_connection)
            finally:
                destination_connection.close()
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    finally:
        source_connection.close()
