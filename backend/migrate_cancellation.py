#!/usr/bin/env python3
"""
Migration: Add 'cancellation_request' action type to agent_actions table.
Run against BOTH local Postgres and Neon.

Usage:
    python migrate_cancellation.py <database_url>

Example:
    # Local dev
    python migrate_cancellation.py "postgresql+psycopg://postgres:devpass@localhost:5432/parcelpilot"

    # Neon production
    python migrate_cancellation.py "postgresql+psycopg://neondb_owner:npg_...@ep-damp-term-aycd8bs8-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
"""

import sys
import os
from sqlalchemy import create_engine, text

def run_migration(database_url: str):
    """Run the migration against the specified database."""

    print(f"Connecting to database...")
    engine = create_engine(database_url, echo=False)

    try:
        with engine.connect() as conn:
            print("Dropping old CHECK constraint...")
            conn.execute(text("""
                ALTER TABLE agent_actions
                DROP CONSTRAINT agent_actions_action_type_check
            """))

            print("Adding new CHECK constraint with 'cancellation_request'...")
            conn.execute(text("""
                ALTER TABLE agent_actions
                ADD CONSTRAINT agent_actions_action_type_check
                    CHECK (action_type IN ('escalation', 'ticket_update', 'follow_up_task', 'cancellation_request'))
            """))

            conn.commit()
            print("✓ Migration successful!")

            # Verify
            result = conn.execute(text("""
                SELECT COUNT(*) as total_actions FROM agent_actions
            """))
            row = result.fetchone()
            print(f"✓ Verified: {row[0]} existing actions remain unchanged")

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    database_url = sys.argv[1]
    run_migration(database_url)
