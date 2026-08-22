"""
Embed document chunks (from chunks.json) using OpenAI text-embedding-3-small
and load into Postgres with vector embeddings.

Run this AFTER chunk_documents.py, once you've reviewed chunks.json.
"""

import json
import os
from pathlib import Path
from openai import OpenAI
from sqlalchemy import text
from config import engine

CHUNKS_FILE = Path(__file__).parent / "chunks.json"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536

def embed_chunk(client: OpenAI, content: str) -> list:
    """Embed a chunk using OpenAI."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=content,
    )
    return response.data[0].embedding

def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("✗ OPENAI_API_KEY not set")
        return

    if not CHUNKS_FILE.exists():
        print(f"✗ {CHUNKS_FILE} not found. Run chunk_documents.py first.")
        return

    print(f"Loading chunks from {CHUNKS_FILE}")
    with open(CHUNKS_FILE, "r") as f:
        chunks = json.load(f)

    print(f"Embedding {len(chunks)} chunks...")

    client = OpenAI(api_key=api_key)

    inserted = 0
    with engine.connect() as conn:
        for i, chunk in enumerate(chunks):
            try:
                # Embed
                embedding = embed_chunk(client, chunk["content"])

                # Insert into database
                sql = """
                INSERT INTO doc_chunks (
                    source_file, doc_type, status, customer_account_id,
                    effective_date, section_number, section_title, content, embedding
                ) VALUES (
                    :source_file, :doc_type, :status, :customer_account_id,
                    :effective_date, :section_number, :section_title, :content, :embedding
                )
                ON CONFLICT DO NOTHING
                """

                params = {
                    "source_file": chunk["source_file"],
                    "doc_type": chunk["doc_type"],
                    "status": chunk["status"],
                    "customer_account_id": chunk["customer_account_id"],
                    "effective_date": chunk["effective_date"],
                    "section_number": chunk["section_number"],
                    "section_title": chunk["section_title"],
                    "content": chunk["content"],
                    "embedding": embedding,
                }

                conn.execute(text(sql), params)
                inserted += 1

                if (i + 1) % 5 == 0:
                    print(f"  {i + 1}/{len(chunks)} chunks embedded and loaded")

            except Exception as e:
                print(f"  ✗ Error embedding chunk {i}: {e}")
                import traceback
                traceback.print_exc()

        conn.commit()

    print(f"\n✓ {inserted} chunks successfully embedded and loaded")

if __name__ == "__main__":
    main()
