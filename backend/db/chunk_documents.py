"""
Chunk the 6 PDFs by their section boundaries (not fixed-token windows).
Output: chunks.json for manual review before embedding.

Rationale: These docs are short (1-2 pages) with clean numbered sections.
Fixed-token chunking risks splitting a rate table from its labels, or a rule
from its exception clause. Chunking by section keeps semantically complete
units together.
"""

import json
from pathlib import Path
import pdfplumber
from datetime import datetime

# Metadata for each PDF
DOCS_METADATA = {
    "01_Support_Policy_v3_CURRENT.pdf": {
        "doc_type": "policy",
        "status": "current",
        "customer_account_id": None,
        "effective_date": "2026-07-01",
    },
    "02_Support_Policy_v2_DEPRECATED.pdf": {
        "doc_type": "policy",
        "status": "deprecated",
        "customer_account_id": None,
        "effective_date": "2026-01-01",
    },
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf": {
        "doc_type": "sop",
        "status": "current",
        "customer_account_id": None,
        "effective_date": "2026-06-15",
    },
    "04_Product_Operations_Guide_and_Known_Issues.pdf": {
        "doc_type": "product_doc",
        "status": "current",
        "customer_account_id": None,
        "effective_date": None,
    },
    "05_Northstar_Logistics_Enterprise_Agreement.pdf": {
        "doc_type": "contract",
        "status": "active",
        "customer_account_id": "ACCT-001",
        "effective_date": "2025-01-01",
    },
    "06_LumenWorks_Service_Agreement.pdf": {
        "doc_type": "contract",
        "status": "active",
        "customer_account_id": "ACCT-002",
        "effective_date": "2025-06-01",
    },
}

def extract_text_from_pdf(pdf_path):
    """Extract full text from PDF using pdfplumber."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
                text += "\n"
        return text
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ""

def chunk_by_sections(text):
    """
    Split text by numbered sections (e.g. "1. Scope", "2. Eligibility", etc).
    Returns list of (section_number, section_title, content) tuples.
    """
    lines = text.split("\n")
    chunks = []
    current_section = None
    current_title = None
    current_content = []

    for line in lines:
        line_stripped = line.strip()

        # Check if this line starts a new section (e.g., "1. Title", "2. Another Title")
        if line_stripped and line_stripped[0].isdigit() and "." in line_stripped:
            parts = line_stripped.split(".", 1)
            try:
                section_num = int(parts[0].strip())
                # This looks like a section header
                if current_section is not None:
                    # Save previous section
                    content = "\n".join(current_content).strip()
                    if content:
                        chunks.append((str(current_section), current_title, content))

                # Start new section
                current_section = section_num
                current_title = parts[1].strip() if len(parts) > 1 else ""
                current_content = []
                continue
            except ValueError:
                pass

        # Accumulate content
        if current_section is not None:
            current_content.append(line)

    # Don't forget the last section
    if current_section is not None:
        content = "\n".join(current_content).strip()
        if content:
            chunks.append((str(current_section), current_title, content))

    return chunks

def main():
    data_dir = Path(__file__).parent.parent.parent
    chunks_output = Path(__file__).parent / "chunks.json"

    all_chunks = []

    for filename, metadata in DOCS_METADATA.items():
        pdf_path = data_dir / filename
        if not pdf_path.exists():
            print(f"⚠ {filename} not found, skipping")
            continue

        print(f"Processing {filename}...")
        text = extract_text_from_pdf(pdf_path)
        sections = chunk_by_sections(text)

        for section_num, section_title, content in sections:
            chunk = {
                "source_file": filename,
                "doc_type": metadata["doc_type"],
                "status": metadata["status"],
                "customer_account_id": metadata["customer_account_id"],
                "effective_date": metadata["effective_date"],
                "section_number": section_num,
                "section_title": section_title,
                "content": content,
                "token_count": len(content.split()),  # Rough estimate
            }
            all_chunks.append(chunk)

    print(f"\nTotal chunks: {len(all_chunks)}")

    # Save to JSON for review
    with open(chunks_output, "w") as f:
        json.dump(all_chunks, f, indent=2)

    print(f"✓ Chunks saved to {chunks_output}")
    print(f"  Review this file before running embed_chunks.py")

if __name__ == "__main__":
    main()
