from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost:5432/parcelpilot")

# Use QueuePool for stable connection pooling with Neon
# Avoid NullPool which closes every connection immediately (causes protocol violations on Render)
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Test connections before using them
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
