from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost:5432/parcelpilot")

# NullPool for dev/testing; use QueuePool for production
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

def get_connection():
    return engine.connect()

def init_db():
    """Initialize database schema. Idempotent."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

    with engine.connect() as conn:
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        # Execute statements one by one (PostgreSQL driver doesn't support multiple statements)
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()
        print("✓ Database schema initialized")
