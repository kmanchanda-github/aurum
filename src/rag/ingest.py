"""CLI tool to ingest seed articles into ChromaDB.

Usage:
    python -m src.rag.ingest --seed-dir src/rag/seed
    python -m src.rag.ingest --seed-dir src/rag/seed --clear
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word-count chunks."""
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return chunks


def parse_markdown(path: Path) -> tuple[str, dict]:
    """Extract title, category, source_url from markdown frontmatter."""
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
            text = parts[2].strip()

    # Infer category from parent directory name
    category = path.parent.name
    meta.setdefault("category", category)
    meta.setdefault("source_title", path.stem.replace("-", " ").replace("_", " ").title())
    meta.setdefault("source_url", "")
    return text, meta


def ingest(seed_dir: str, clear: bool = False) -> None:
    from src.rag.chroma_store import ChromaStore, Document

    store = ChromaStore()
    if clear:
        print("Clearing existing collection...")
        store._col.delete(where={"category": {"$in": ["investing", "portfolio", "tax", "goals", "market"]}})

    seed_path = Path(seed_dir)
    if not seed_path.exists():
        print(f"Seed directory not found: {seed_dir}", file=sys.stderr)
        sys.exit(1)

    docs: list[Document] = []
    for md_file in sorted(seed_path.rglob("*.md")):
        text, meta = parse_markdown(md_file)
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            doc_id = hashlib.sha256(f"{md_file}:{i}".encode()).hexdigest()[:16]
            docs.append(
                Document(
                    content=chunk,
                    metadata={**meta, "chunk_idx": i, "total_chunks": len(chunks)},
                    doc_id=doc_id,
                )
            )
        print(f"  {md_file.relative_to(seed_path)} → {len(chunks)} chunk(s)")

    if docs:
        store.add_documents(docs)
        print(f"\nIngested {len(docs)} chunks from {seed_path}")
        print(f"Total documents in store: {store.count()}")
    else:
        print("No .md files found to ingest.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest financial education articles into ChromaDB")
    parser.add_argument("--seed-dir", default="src/rag/seed", help="Directory of .md files")
    parser.add_argument("--clear", action="store_true", help="Clear existing documents before ingesting")
    args = parser.parse_args()
    ingest(args.seed_dir, clear=args.clear)
