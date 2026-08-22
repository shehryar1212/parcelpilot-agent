import psycopg

DATABASE_URL = "postgresql://neondb_owner:npg_KWPT1X0eLSot@ep-damp-term-aycd8bs8-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        # Get all contracts
        cur.execute("""
            SELECT customer_account_id, section_title, content
            FROM doc_chunks
            WHERE doc_type = 'contract' AND customer_account_id IS NOT NULL
            ORDER BY customer_account_id, section_number
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"\nAccount: {row[0]}")
            print(f"Section: {row[1]}")
            print(f"Content (first 200 chars): {row[2][:200]}...")
            print("-" * 60)
