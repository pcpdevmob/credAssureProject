"""Alembic env for corpus.db (scope #29). Run via credassure.ledger.migrate, not the alembic CLI."""

from alembic import context

from credassure.ledger.models import CorpusBase

config = context.config
connection = config.attributes["connection"]
context.configure(
    connection=connection,
    target_metadata=CorpusBase.metadata,
    render_as_batch=True,  # SQLite cannot ALTER most columns in place
)
with context.begin_transaction():
    context.run_migrations()
