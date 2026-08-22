import psycopg

DATABASE_URL = "postgresql://neondb_owner:npg_KWPT1X0eLSot@ep-damp-term-aycd8bs8-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT section_title, content
            FROM doc_chunks
            WHERE doc_type='policy' AND status='current' AND customer_account_id IS NULL
            ORDER BY section_number
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"Section: {row[0]}")
            print(f"Content:\n{row[1][:500]}")
            print("\n" + "="*60 + "\n")
