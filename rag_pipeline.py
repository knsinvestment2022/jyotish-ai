"""
RAG Pipeline — run this ONCE to index all Vedic astrology books.

Usage:
    python rag_pipeline.py

This script:
  1. Reads all PDFs from ../Vedic_Astrology/
  2. Splits text into ~400-word chunks
  3. Embeds each chunk with a free local model (all-MiniLM-L6-v2)
  4. Stores everything in ChromaDB at ./chroma_db/

After running, the chat API uses chroma_db/ to find relevant passages.
"""

import os
import re
import time
from pathlib import Path

# --- Paths -----------------------------------------------------------------
VEDIC_DIR = Path(__file__).parent.parent / "Vedic_Astrology"
CHROMA_DIR = Path(__file__).parent / "chroma_db"

# Book titles for clean citations (filename stem → display name)
BOOK_TITLES = {
    "Hindu-Predictive-Astrology-BV-Raman": "Hindu Predictive Astrology – B.V. Raman",
    "Jyotish-Elements-of-Vedic-Astrology-K-S-Charak": "Elements of Vedic Astrology – K.S. Charak",
    "Gayatri-Devi-Vasudev-Advanced-Principles": "Advanced Principles – Gayatri Devi Vasudev",
    "Advanced-Predictive-Astrology-Vol-1": "Advanced Predictive Astrology Vol.1 – Chatterjee",
    "Jyotish-Advanced-Medical-Astrology-Chatterjee": "Medical Astrology – Chatterjee",
    "Fortune-and-Finance-Chatterjee": "Fortune & Finance – Chatterjee",
    "Advanced-Predictive-Techniques-of-Ashtakvarga": "Ashtakvarga – Mehta & Dadwal",
    "Jyotish-Astro-Secrets-KP-Part1": "KP Astro Secrets – Shanmugam",
    "Jyotish-KP-1995-Hariharan-Krishnamurthi-Padhdhati": "KP Paddhati – Hariharan",
    "varshphal-354": "Varshphal / Solar Return – Dr. S.P. Gaur",
    "An-Intro-to-Vedic-Astro-Beckman": "Intro to Vedic Astrology – Beckman",
    "A-Thousand-Suns-Linda-Johnsen": "A Thousand Suns – Linda Johnsen",
    "Death-in-Vedic-Astrology": "Death in Vedic Astrology – Dokras",
    "Example-of-Nadi-Analysis-Umang-Taneja": "Nadi Analysis – Umang Taneja",
    "246218940-231215454-Esoteric-Principles-of-Vedic-Astrology-Bepin-Bihari": "Esoteric Principles – Bepin Bihari",
    "868446240-Jyotish-2021-Himanshu-Shangari-Important-Yogas-in-Vedic-Astrology-Part-1-Denis-Chevalier-Z-Library": "Important Yogas – Himanshu Shangari",
    "408206024-Jyotish-2009-K-K-Pathak-Classical-Predictive-Techniques-Vol-1-pdf": "Classical Predictive Techniques – K.K. Pathak",
    "481615549-Mandala-BOOK-III-NAKSHATRA-in-Vedic-Astrology": "Nakshatra in Vedic Astrology – Dokras",
    "868446388-Jyotisha-Viveka-Chudamani-Vol-2-Rashmika-K-Janardhana-Rao-Z-Library": "Jyotisha Viveka Chudamani Vol.2 – Janardhana Rao",
}


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 60) -> list[str]:
    """Split text into overlapping word chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if len(chunk.strip()) > 100:  # skip tiny chunks
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def clean_text(text: str) -> str:
    """Remove PDF artefacts."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # remove non-ASCII
    text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)  # fix hyphenation
    return text.strip()


def get_display_title(pdf_path: Path) -> str:
    stem = pdf_path.stem
    for key, title in BOOK_TITLES.items():
        if key in stem:
            return title
    return stem[:60]  # fallback: first 60 chars of filename


def build_index():
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        print("ERROR: Install dependencies first:\n  pip install chromadb sentence-transformers pypdf")
        return

    try:
        from pypdf import PdfReader
    except ImportError:
        print("ERROR: pip install pypdf")
        return

    print("Setting up ChromaDB...")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Use free local embedding model
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    # Delete existing collection to rebuild fresh
    try:
        client.delete_collection("vedic_books")
    except Exception:
        pass

    collection = client.create_collection(
        name="vedic_books",
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"},
    )

    pdf_files = list(VEDIC_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {VEDIC_DIR}\n")

    total_chunks = 0
    chunk_ids = []
    chunk_texts = []
    chunk_metas = []

    for pdf_path in sorted(pdf_files):
        title = get_display_title(pdf_path)
        print(f"Reading: {title}")
        try:
            reader = PdfReader(str(pdf_path))
            full_text = ""
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    full_text += " " + t

            full_text = clean_text(full_text)
            chunks = chunk_text(full_text)
            print(f"  → {len(chunks)} chunks")

            for i, chunk in enumerate(chunks):
                chunk_id = f"{pdf_path.stem}_{i}"
                chunk_ids.append(chunk_id)
                chunk_texts.append(chunk)
                chunk_metas.append({
                    "source": title,
                    "file": pdf_path.name,
                    "chunk_index": i,
                })
            total_chunks += len(chunks)

        except Exception as e:
            print(f"  ERROR: {e}")

    # Add all at once in batches of 500
    print(f"\nAdding {total_chunks} chunks to ChromaDB...")
    batch_size = 500
    for i in range(0, len(chunk_ids), batch_size):
        collection.add(
            ids=chunk_ids[i : i + batch_size],
            documents=chunk_texts[i : i + batch_size],
            metadatas=chunk_metas[i : i + batch_size],
        )
        print(f"  Indexed {min(i + batch_size, total_chunks)}/{total_chunks}...")
        time.sleep(0.5)  # avoid CPU spike

    print(f"\nDone! ChromaDB index saved to: {CHROMA_DIR}")
    print(f"Total chunks indexed: {total_chunks}")
    print("\nYou can now start the Flask app.")


if __name__ == "__main__":
    build_index()
