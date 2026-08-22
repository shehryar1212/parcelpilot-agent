import psycopg

DATABASE_URL = "postgresql://neondb_owner:npg_KWPT1X0eLSot@ep-damp-term-aycd8bs8-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT t.ticket_id, t.account_id, a.account_name, t.created_at, t.subject
            FROM tickets t
            LEFT JOIN accounts a ON t.account_id = a.account_id
            WHERE t.ticket_id = 'TKT-505'
        """)
        row = cur.fetchone()
        if row:
            print(f"Ticket: {row[0]}")
            print(f"Account ID: {row[1]}")
            print(f"Account Name: {row[2]}")
            print(f"Created: {row[3]}")
            print(f"Subject: {row[4]}")
        else:
            print("Ticket not found")
