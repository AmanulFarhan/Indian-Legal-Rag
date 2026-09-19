import os
import time
from pathlib import Path
from typing import List, Dict
import json

import fitz
from dotenv import load_dotenv
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# ============================================================
# CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]

PINECONE_INDEX = os.getenv(
    "PINECONE_INDEX",
    "indian-legal-rag"
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "gemini-embedding-001"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

TOP_K = int(os.getenv("TOP_K", "5"))

# Your Pinecone index is configured for 768 dimensions
EMBEDDING_DIMENSION = 384

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


# ============================================================
# CLIENTS
# ============================================================

_embedder = None
_gemini = None
_pc = None
_index = None

def embedder():
    global _embedder

    if _embedder is None:
        print(
            f"Loading embedding model: {EMBEDDING_MODEL}"
        )

        _embedder = SentenceTransformer(
            EMBEDDING_MODEL
        )

    return _embedder


def gemini_client():
    global _gemini

    if _gemini is None:
        _gemini = genai.Client(
            api_key=GEMINI_API_KEY
        )

    return _gemini


def pinecone_index():
    global _pc, _index

    if _index is None:
        _pc = Pinecone(
            api_key=PINECONE_API_KEY
        )

        _index = _pc.Index(
            PINECONE_INDEX
        )

    return _index


# ============================================================
# PDF EXTRACTION
# ============================================================

def extract_pdf(path: Path) -> List[Dict]:
    """
    Extract text page-by-page.

    Page numbers are preserved so that retrieved legal
    information can be traced back to the source document.
    """

    doc = fitz.open(path)

    pages = []

    for page_number, page in enumerate(doc, start=1):

        text = page.get_text("text")

        if text.strip():

            pages.append({
                "page": page_number,
                "text": text
            })

    doc.close()

    return pages


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:
    """
    Basic normalization of extracted PDF text.
    """

    lines = []

    for line in text.splitlines():

        line = " ".join(line.split())

        if line:
            lines.append(line)

    return "\n".join(lines)


# ============================================================
# CHUNKING
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> List[str]:

    words = text.split()

    if not words:
        return []

    chunks = []

    step = chunk_size - overlap

    for start in range(0, len(words), step):

        part = words[
            start:start + chunk_size
        ]

        # Ignore very small final chunks
        if len(part) < 40:
            break

        chunks.append(
            " ".join(part)
        )

    return chunks


# ============================================================
# DOCUMENT NAMES
# ============================================================

def document_name(filename: str) -> str:

    names = {

        "bns.pdf":
            "Bharatiya Nyaya Sanhita, 2023",

        "bnss.pdf":
            "Bharatiya Nagarik Suraksha Sanhita, 2023",

        "bsa.pdf":
            "Bharatiya Sakshya Adhiniyam, 2023",

        "contract.pdf":
            "Indian Contract Act, 1872",

        "rti.pdf":
            "Right to Information Act, 2005",

        "constitution.pdf":
            "Constitution of India",

        "consumer_protection.pdf":
            "Consumer Protection Act, 2019",
    }

    return names.get(
        filename,
        Path(filename).stem.replace(
            "_", " "
        ).title()
    )


# ============================================================
# BUILD LEGAL CHUNKS
# ============================================================

def build_chunks():

    all_chunks = []

    pdf_files = sorted(
        RAW.glob("*.pdf")
    )

    if not pdf_files:
        raise RuntimeError(
            f"No PDF files found in {RAW}"
        )

    for path in pdf_files:

        print(
            f"\nProcessing: {path.name}"
        )

        pages = extract_pdf(path)

        document = document_name(
            path.name
        )

        document_chunks = 0

        for page_data in pages:

            page_number = page_data["page"]

            text = clean_text(
                page_data["text"]
            )

            chunks = chunk_text(text)

            for local_chunk, chunk in enumerate(
                chunks
            ):

                chunk_id = (
                    f"{path.stem}"
                    f"-p{page_number}"
                    f"-c{local_chunk}"
                )

                all_chunks.append({

                    "id": chunk_id,

                    "text": chunk,

                    "source": path.name,

                    "document": document,

                    "page": page_number,

                    "chunk": local_chunk,
                })

                document_chunks += 1

        print(
            f"  Pages: {len(pages)}"
        )

        print(
            f"  Chunks: {document_chunks}"
        )

    print(
        f"\nTotal chunks: {len(all_chunks)}"
    )

    return all_chunks


# ============================================================
# GEMINI EMBEDDINGS
# ============================================================

def generate_embeddings(
    texts: List[str]
):

    print(
        f"Generating local embeddings for "
        f"{len(texts)} chunks..."
    )

    model = embedder()

    embeddings = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    return embeddings.tolist()


# ============================================================
# INGESTION
# ============================================================

def ingest():

    print("=" * 60)
    print("INDIAN LEGAL RAG - DOCUMENT INGESTION")
    print("=" * 60)

    # --------------------------------------------------------
    # STEP 1
    # --------------------------------------------------------

    print(
        "\n[1/3] Extracting and chunking legal documents..."
    )

    chunks = build_chunks()

    # --------------------------------------------------------
    # STEP 2
    # --------------------------------------------------------

    print(
        "\n[2/3] Generating Gemini embeddings..."
    )

    texts = [
        item["text"]
        for item in chunks
    ]

    embeddings = generate_embeddings(texts)

    # --------------------------------------------------------
    # STEP 3
    # --------------------------------------------------------

    print(
        "\n[3/3] Uploading vectors to Pinecone..."
    )

    index = pinecone_index()

    vectors = []

    for item, embedding in zip(
        chunks,
        embeddings
    ):

        metadata = {

            "text":
                item["text"],

            "source":
                item["source"],

            "document":
                item["document"],

            "page":
                item["page"],

            "chunk":
                item["chunk"],
        }

        vectors.append({

            "id":
                item["id"],

            "values":
                embedding,

            "metadata":
                metadata
        })

    batch_size = 100

    total = len(vectors)

    for start in range(
        0,
        total,
        batch_size
    ):

        batch = vectors[
            start:start + batch_size
        ]

        print(
            f"Uploading vectors "
            f"{start + 1}-"
            f"{min(start + batch_size, total)} "
            f"of {total}"
        )

        index.upsert(
            vectors=batch
        )

    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)

    print(
        f"Total chunks: {total}"
    )

    print(
        f"Pinecone index: {PINECONE_INDEX}"
    )

    print(
        f"Embedding model: {EMBEDDING_MODEL}"
    )

    print(
        f"Embedding dimension: "
        f"{EMBEDDING_DIMENSION}"
    )


# ============================================================
# RETRIEVAL
# ============================================================

def retrieve(
    question: str,
    top_k: int = TOP_K
) -> List[Dict]:

    print(
        "\nGenerating query embedding..."
    )

    query_vector = embedder().encode(
        [question],
        normalize_embeddings=True
    )[0].tolist()

    print(
        f"Searching Pinecone "
        f"(top_k={top_k})..."
    )

    result = pinecone_index().query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True
    )

    hits = []

    for match in result["matches"]:

        metadata = match["metadata"]

        hits.append({
            **metadata,
            "score": float(match["score"])
        })

    return hits


# ============================================================
# RAG ANSWERING
# ============================================================

def answer(question: str, top_k: int = TOP_K):
    retrieved = retrieve(question, top_k)

    context_parts = []

    for i, item in enumerate(retrieved, 1):
        context_parts.append(
            f"""
SOURCE {i}
Document: {item['source']}
Page: {item['page']}
Similarity: {item['score']:.4f}

{item['text']}
"""
        )

    context = "\n".join(context_parts)

    prompt = f"""
You are an AI assistant for Indian legal awareness.

Answer the user's question using ONLY the retrieved legal context below.

Rules:
1. Do not invent laws, sections, cases, or legal facts.
2. If the retrieved context is insufficient, clearly say so.
3. Give a clear and understandable explanation.
4. Mention the relevant Act or document when supported by the context.
5. This is general legal information, not professional legal advice.

RETRIEVED LEGAL CONTEXT:
{context}

USER QUESTION:
{question}

ANSWER:
"""

    response = gemini_client().models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=prompt
    )

    return {
        "answer": response.text,
        "sources": retrieved
    }

def extract_document_text(file_path: str) -> str:
    """
    Extract text from a PDF document.
    """
    doc = fitz.open(file_path)

    pages = []

    for page_number, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()

        if text:
            pages.append(
                f"\n--- Page {page_number} ---\n{text}"
            )

    doc.close()

    return "\n".join(pages)


def analyze_document(text: str):
    prompt = f"""
    You are an AI assistant for Indian legal awareness.

    Analyze the following legal document.

    Return ONLY valid JSON.
    Do NOT use Markdown.
    Do NOT wrap the JSON in ```json or ```.

    Use exactly this schema:

    {{
    "document_type": "",
    "concise_summary": "",
    "parties_or_entities_mentioned": [],
    "important_sections_or_clauses": [],
    "key_obligations": [],
    "important_dates": [],
    "financial_terms": [],
    "potentially_important_legal_points": []
    }}

    Rules:
    - Use only information present in the document.
    - Do not invent information.
    - If information is unavailable, use "Not specified".
    - Keep extracted facts separate from interpretation.
    - This is general legal information, not professional legal advice.

    DOCUMENT:
    {text}
    """
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = gemini_client().models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            return json.loads(response.text)

        except Exception as e:
            error_text = str(e)

            if "503" not in error_text and "UNAVAILABLE" not in error_text:
                raise

            if attempt == max_retries - 1:
                raise

            wait_time = 2 ** attempt
            print(
                f"Gemini temporarily unavailable. "
                f"Retrying in {wait_time} seconds..."
            )
            time.sleep(wait_time)