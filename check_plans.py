import psycopg

DATABASE_URL = "postgresql://neondb_owner:npg_KWPT1X0eLSot@ep-damp-term-aycd8bs8-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT account_id, account_name, plan FROM accounts ORDER BY account_id")
        for row in cur.fetchall():
            print(f"{row[0]}: {row[1]} - Plan: {row[2]}")
