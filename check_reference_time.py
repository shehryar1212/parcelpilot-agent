import psycopg

DATABASE_URL = "postgresql://neondb_owner:npg_KWPT1X0eLSot@ep-damp-term-aycd8bs8-pooler.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require"

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT key, value FROM dataset_meta WHERE key = 'snapshot_at'")
        row = cur.fetchone()
        if row:
            print(f"Key: {row[0]}")
            print(f"Value: {row[1]}")
            print(f"Type: {type(row[1])}")
        else:
            print("snapshot_at not found in dataset_meta!")
