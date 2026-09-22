import os
import time
import re
import hashlib
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
INGESTION_REGISTRY = ROOT / "data" / "ingestion_registry.json"

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
    "sentence-transformers/all-MiniLM-L6-v2"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

TOP_K = int(os.getenv("TOP_K", "5"))
CONVERSATION_HISTORY_LIMIT = max(
    2,
    min(int(os.getenv("CONVERSATION_HISTORY_LIMIT", "8")), 20)
)

# all-MiniLM-L6-v2 produces 384-dimensional local Sentence Transformer vectors.
EMBEDDING_DIMENSION = 384

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

DOCUMENT_TITLES = {
    "bns.pdf": "Bharatiya Nyaya Sanhita, 2023",
    "bnss.pdf": "Bharatiya Nagarik Suraksha Sanhita, 2023",
    "bsa.pdf": "Bharatiya Sakshya Adhiniyam, 2023",
    "contract.pdf": "Indian Contract Act, 1872",
    "rti.pdf": "Right to Information Act, 2005",
    "constitution.pdf": "Constitution of India, 1950",
    "consumer_protection.pdf": "Consumer Protection Act, 2019",
}

NUMBERED_PROVISION_HEADING = re.compile(
    r"(?<![A-Za-z0-9])(?P<number>\d{1,3}[A-Z]?)\.\s+"
    r"(?=(?:[\"“]|[A-Z]))"
    r"(?:[\"“][^\"”]+[\"”]\s*)?[A-Za-z][^.\n—-]{1,120}(?:\.|—|-)",
)
EXPLICIT_PROVISION_REFERENCE = re.compile(
    r"\b(?P<kind>section|article)\s+(?P<number>\d{1,3}[A-Z]?)\b",
    re.IGNORECASE,
)


# ============================================================
# CLIENTS
# ============================================================

_embedder = None
_gemini = None
_pc = None
_index = None


def pipeline_log(stage: str, message: str):
    """Print concise operational progress without exposing document contents or keys."""

    print(f"[{stage}] {message}")


def embedder():
    global _embedder

    if _embedder is None:
        pipeline_log("Embedding", f"Loading local Sentence Transformer model: {EMBEDDING_MODEL}")

        _embedder = SentenceTransformer(
            EMBEDDING_MODEL
        )

    return _embedder


def gemini_client():
    global _gemini

    if _gemini is None:
        # Gemini is used for language tasks and answer generation, not embeddings.
        pipeline_log("Gemini", f"Initializing generation client for model: {GEMINI_MODEL}")
        _gemini = genai.Client(
            api_key=GEMINI_API_KEY
        )

    return _gemini
def contains_malayalam(text: str) -> bool:
    """
    Return True when the text contains at least one Malayalam character.
    """

    return any(
        "\u0D00" <= character <= "\u0D7F"
        for character in text
    )


def determine_response_language(
    question: str = "",
    requested_language: str = "auto"
) -> str:
    """
    Decide whether Gemini should answer in English or Malayalam.
    """

    requested_language = requested_language.strip().lower()

    if requested_language not in {
        "auto",
        "english",
        "malayalam"
    }:
        raise ValueError(
            "Language must be auto, English, or Malayalam."
        )

    if requested_language == "english":
        return "English"

    if requested_language == "malayalam":
        return "Malayalam"

    # Automatic selection
    if contains_malayalam(question):
        return "Malayalam"

    return "English"


def translate_query_to_english(question: str) -> str:
    """
    Translate a Malayalam retrieval query into English.

    English queries are returned without making a Gemini request.
    """

    question = question.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    if not contains_malayalam(question):
        pipeline_log("Translation", "Question is already English; skipping translation.")
        return question

    pipeline_log("Translation", "Malayalam detected; requesting an English retrieval translation from Gemini.")

    prompt = f"""
Translate the Malayalam legal question below into English for semantic
information retrieval.

Rules:
- Preserve article numbers and section numbers.
- Preserve names of laws, courts, institutions, and people.
- Preserve conditions, exceptions, and negation.
- Do not answer the question.
- Do not explain the translation.
- Return only the English translation.

MALAYALAM QUESTION:
{question}

ENGLISH TRANSLATION:
"""

    response = gemini_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    translation = (response.text or "").strip()

    if not translation:
        raise RuntimeError(
            "Gemini returned an empty query translation."
        )

    pipeline_log("Translation", "English retrieval translation completed.")
    return translation

def pinecone_index():
    global _pc, _index

    if _index is None:
        pipeline_log("Pinecone", f"Connecting to existing index: {PINECONE_INDEX}")
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
    return DOCUMENT_TITLES.get(
        filename,
        Path(filename).stem.replace(
            "_", " "
        ).title()
    )


# ============================================================
# PDF HASHING AND CHUNK PREPARATION
# ============================================================

def pdf_content_hash(path: Path) -> str:
    """Return a stable SHA-256 identity for a PDF's bytes."""

    pipeline_log("Ingestion", f"Calculating SHA-256 for {path.name}")
    digest = hashlib.sha256()

    with path.open("rb") as pdf_file:
        for block in iter(lambda: pdf_file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def load_ingestion_registry(registry_path: Path = INGESTION_REGISTRY) -> Dict:
    """Load the successful-ingestion registry, creating its shape in memory."""

    if not registry_path.exists():
        return {"version": 1, "documents": {}}

    with registry_path.open("r", encoding="utf-8") as registry_file:
        registry = json.load(registry_file)

    if not isinstance(registry, dict) or not isinstance(registry.get("documents"), dict):
        raise RuntimeError(f"Invalid ingestion registry: {registry_path}")

    return registry


def save_ingestion_registry(registry: Dict, registry_path: Path = INGESTION_REGISTRY):
    """Persist successful hashes atomically after a document has fully uploaded."""

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = registry_path.with_suffix(".tmp")

    with temporary_path.open("w", encoding="utf-8") as registry_file:
        json.dump(registry, registry_file, indent=2, sort_keys=True)
        registry_file.flush()
        os.fsync(registry_file.fileno())

    temporary_path.replace(registry_path)


def build_document_chunks(path: Path, document_hash: str) -> List[Dict]:
    """Extract and chunk one PDF, using the content hash in new vector IDs."""

    pipeline_log("Ingestion", f"Extracting text from {path.name}")
    pages = extract_pdf(path)
    pipeline_log("Ingestion", f"Extracted {len(pages)} non-empty page(s) from {path.name}")
    document = document_name(path.name)
    document_chunks = []

    for page_data in pages:
        page_number = page_data["page"]
        text = clean_text(page_data["text"])

        for local_chunk, chunk in enumerate(chunk_text(text)):
            document_chunks.append({
                "id": f"{path.stem}-{document_hash[:12]}-p{page_number}-c{local_chunk}",
                "text": chunk,
                "source": path.name,
                "document": document,
                "page": page_number,
                "chunk": local_chunk,
            })

    pipeline_log("Ingestion", f"Created {len(document_chunks)} chunk(s) for {path.name}")
    return document_chunks


def build_chunks(paths: List[Path] | None = None):

    all_chunks = []

    pdf_files = paths if paths is not None else sorted(RAW.glob("*.pdf"))

    if not pdf_files:
        raise RuntimeError(
            f"No PDF files found in {RAW}"
        )

    for path in pdf_files:

        print(
            f"\nProcessing: {path.name}"
        )

        document_chunks = build_document_chunks(path, pdf_content_hash(path))
        all_chunks.extend(document_chunks)

        print(
            f"  Chunks: {len(document_chunks)}"
        )

    print(
        f"\nTotal chunks: {len(all_chunks)}"
    )

    return all_chunks


# ============================================================
# LOCAL SENTENCE TRANSFORMER EMBEDDINGS
# ============================================================

def generate_embeddings(
    texts: List[str]
):

    # Embeddings are generated locally with Sentence Transformers, not Gemini.
    pipeline_log("Embedding", f"Generating local embeddings for {len(texts)} chunk(s)")

    model = embedder()

    embeddings = model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    pipeline_log("Embedding", f"Generated {len(embeddings)} normalized {EMBEDDING_DIMENSION}-dimension vector(s)")
    return embeddings.tolist()


# ============================================================
# INGESTION
# ============================================================

def vectors_for_chunks(chunks: List[Dict], embeddings: List[List[float]]) -> List[Dict]:
    """Build Pinecone vectors without changing the existing metadata schema."""

    vectors = []

    for item, embedding in zip(chunks, embeddings):
        vectors.append({
            "id": item["id"],
            "values": embedding,
            "metadata": {
                "text": item["text"],
                "source": item["source"],
                "document": item["document"],
                "page": item["page"],
                "chunk": item["chunk"],
            }
        })

    return vectors


def ingest(
    raw_directory: Path = RAW,
    registry_path: Path = INGESTION_REGISTRY
):

    print("=" * 60)
    print("INDIAN LEGAL RAG - DOCUMENT INGESTION")
    print("=" * 60)

    pdf_files = sorted(raw_directory.glob("*.pdf"))
    if not pdf_files:
        raise RuntimeError(f"No PDF files found in {raw_directory}")

    pipeline_log("Ingestion", f"Discovered {len(pdf_files)} PDF file(s) in {raw_directory}")
    pipeline_log("Registry", f"Loading successful-ingestion registry: {registry_path}")
    registry = load_ingestion_registry(registry_path)
    index = None
    processed = 0
    skipped = 0
    failed = []
    total = 0

    for path in pdf_files:
        document_hash = pdf_content_hash(path)

        if document_hash in registry["documents"]:
            pipeline_log("Ingestion", f"Skipping {path.name}: already registered (SHA-256 {document_hash[:12]}...)")
            skipped += 1
            continue

        try:
            pipeline_log("Ingestion", f"Processing {path.name} (SHA-256 {document_hash[:12]}...)")
            chunks = build_document_chunks(path, document_hash)
            if not chunks:
                raise RuntimeError("No indexable text chunks were extracted.")

            embeddings = generate_embeddings([item["text"] for item in chunks])
            vectors = vectors_for_chunks(chunks, embeddings)
            pipeline_log("Ingestion", f"Prepared {len(vectors)} Pinecone vector(s) for {path.name}")
            index = index or pinecone_index()

            for start in range(0, len(vectors), 100):
                batch = vectors[start:start + 100]
                pipeline_log("Pinecone", f"Upserting {path.name}: vectors {start + 1}-{min(start + 100, len(vectors))} of {len(vectors)}")
                index.upsert(vectors=batch)

            registry["documents"][document_hash] = {
                "source": path.name,
                "chunk_count": len(chunks),
            }
            save_ingestion_registry(registry, registry_path)
            pipeline_log("Registry", f"Recorded successful hash for {path.name}")
            processed += 1
            total += len(chunks)
            pipeline_log("Ingestion", f"Completed {path.name}: {len(chunks)} chunk(s) uploaded")

        except Exception as error:
            failed.append(path.name)
            pipeline_log("Ingestion", f"Failed {path.name}: {error}. It was not registered and can be retried.")

    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)

    print(
        f"New chunks uploaded: {total}"
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

    pipeline_log("Ingestion", f"Documents processed: {processed}; skipped: {skipped}; failed: {len(failed)}")

    if failed:
        raise RuntimeError(f"Ingestion failed for: {', '.join(failed)}")


# ============================================================
# RETRIEVAL
# ============================================================

def source_document_title(source: str, document: str = "") -> str:
    """Return the canonical user-facing title for a known corpus file."""

    return DOCUMENT_TITLES.get(source.lower(), document or source or "Legal source")


def provision_from_passage(
    text: str,
    source: str,
    document: str = ""
) -> str | None:
    """Return a provision only when it is explicitly present in passage text."""

    if not text:
        return None

    source_is_constitution = source.lower() == "constitution.pdf"
    explicit_match = EXPLICIT_PROVISION_REFERENCE.search(text)

    if explicit_match:
        kind = "Article" if source_is_constitution else "Section"
        return f"{kind} {explicit_match.group('number')}"

    heading_match = NUMBERED_PROVISION_HEADING.search(text)
    if not heading_match:
        return None

    kind = "Article" if source_is_constitution else "Section"
    return f"{kind} {heading_match.group('number')}"


def format_source_citation(item: Dict) -> str:
    """Format a source for users without exposing internal PDF page numbers."""

    title = source_document_title(
        str(item.get("source", "")),
        str(item.get("document", ""))
    )
    provision = item.get("provision") or provision_from_passage(
        str(item.get("text", "")),
        str(item.get("source", "")),
        str(item.get("document", ""))
    )

    return f"{title} — {provision}" if provision else title

def retrieve(
    question: str,
    top_k: int = TOP_K
) -> List[Dict]:

    # The query is embedded locally with the same Sentence Transformer model.
    pipeline_log("Retrieval", f"Generating local query embedding (top_k={top_k})")

    query_vector = embedder().encode(
        [question],
        normalize_embeddings=True
    )[0].tolist()

    pipeline_log("Retrieval", f"Searching Pinecone index {PINECONE_INDEX}")

    result = pinecone_index().query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True
    )

    hits = []

    for match in result["matches"]:

        metadata = dict(match["metadata"])
        metadata["provision"] = provision_from_passage(
            str(metadata.get("text", "")),
            str(metadata.get("source", "")),
            str(metadata.get("document", ""))
        )
        metadata["citation"] = format_source_citation(metadata)

        hits.append({
            **metadata,
            "score": float(match["score"])
        })

    pipeline_log("Retrieval", f"Retrieved {len(hits)} matching legal passage(s)")
    return hits


# ============================================================
# RAG ANSWERING
# ============================================================

def contextualize_question(
    question: str,
    conversation_history: List[Dict]
) -> str:
    """Rewrite a follow-up as a standalone retrieval question."""

    recent_history = conversation_history[-CONVERSATION_HISTORY_LIMIT:]
    formatted_history = "\n".join(
        f"{message['role'].title()}: {message['content'].strip()}"
        for message in recent_history
        if message.get("role") in {"user", "assistant"}
        and message.get("content", "").strip()
    )

    if not formatted_history:
        pipeline_log("Conversation", "No usable prior messages; using the original question for retrieval.")
        return question

    pipeline_log("Conversation", f"Rewriting follow-up with {len(recent_history)} recent message(s)")

    prompt = f"""
Rewrite the user's latest question as one standalone legal retrieval question.

Use the conversation only to resolve references such as "it", "this", "that",
or an omitted legal concept. Preserve the user's intended scope. Do not answer
the question, add legal facts, or mention the conversation. Return only the
standalone question in English.

CONVERSATION:
{formatted_history}

LATEST USER QUESTION:
{question}

STANDALONE RETRIEVAL QUESTION:
"""

    response = gemini_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )
    contextualized_question = (response.text or "").strip()

    if not contextualized_question:
        raise RuntimeError("Gemini returned an empty contextualized question.")

    pipeline_log("Conversation", "Standalone retrieval question created.")
    return contextualized_question

def answer(
    question: str,
    top_k: int = TOP_K,
    output_language: str = "auto",
    conversation_history: List[Dict] | None = None
):
    original_question = question.strip()

    if not original_question:
        raise ValueError("Question cannot be empty.")

    pipeline_log("RAG", f"Received question; history messages: {len(conversation_history or [])}; requested top_k: {top_k}")

    # First questions keep the existing retrieval path; follow-ups are rewritten first.
    if conversation_history:
        standalone_question = contextualize_question(
            original_question,
            conversation_history
        )
        retrieval_question = translate_query_to_english(standalone_question)
    else:
        # Malayalam becomes English. English remains unchanged.
        retrieval_question = translate_query_to_english(original_question)

    contextual_question_section = ""
    if conversation_history:
        contextual_question_section = f"""
CONTEXTUALIZED QUESTION USED FOR RETRIEVAL:
{standalone_question}
"""

    answer_language = determine_response_language(
        question=original_question,
        requested_language=output_language
    )

    pipeline_log("RAG", f"Response language resolved to {answer_language}")
    # Pinecone is searched with the English original or contextualized query.
    retrieved = retrieve(
        retrieval_question,
        top_k
    )

    context_parts = []

    for number, item in enumerate(retrieved, start=1):
        context_parts.append(
            f"""
[S{number}]
Document: {item.get('document', item.get('source', 'Unknown'))}
Source file: {item.get('source', 'Unknown')}
Page: {item.get('page', 'Unknown')}
Similarity: {item.get('score', 0):.4f}

{item.get('text', '')}
""".strip()
        )

    context = "\n\n".join(context_parts)
    pipeline_log("RAG", f"Built grounded prompt context from {len(retrieved)} retrieved passage(s)")

    prompt = f"""
You are a careful Indian legal information assistant teaching a reader who
has no previous legal knowledge.

Answer using only the retrieved legal passages supplied below. Your goal is
to help the reader understand the law clearly and accurately, not merely list
provisions.

ACCURACY AND SCOPE RULES:
1. Answer in {answer_language}.
2. Do not treat related legal terms as identical. For example, "human
   rights" is broader than "Fundamental Rights". Explain the distinction
   only when it is relevant to the user's question and supported by the
   retrieved passages.
3. Never imply that the retrieved documents are the whole of Indian law.
   For a broad question, clearly state the scope of the available evidence.
4. Use only the supplied passages for legal claims. Do not invent or add
   laws, sections, cases, penalties, procedures, remedies, or facts.
5. Preserve important conditions, exceptions, qualifications, and limitations
   found in the passages.
6. Cite each substantive legal claim immediately with one or more supplied
   labels, such as [S1] or [S1, S3]. Do not cite a passage that does not
   support the claim.
7. If evidence is missing or only partially answers the question, explain
   exactly what can be answered and what cannot be confirmed from the
   retrieved documents.
8. Keep citation labels unchanged when answering in Malayalam.
9. Stay focused on the user's actual question. Do not introduce another
   legal topic, law, offence, remedy, or legal context merely because a
   retrieved passage contains related information.
10. For follow-up questions, use the previous conversation to understand
    what the user means. Prefer the legal context established by the
    conversation unless the user explicitly changes the topic.
11. Do not broaden a narrow follow-up question into a general article.
    Include additional legal context only when it is necessary to answer
    the question accurately.

WRITING AND DETAIL RULES:
1. Determine the appropriate answer length from the user's question.
2. For a narrow question or short follow-up:
   - Answer the question directly in the first 1-2 sentences.
   - Give only the most relevant supporting legal points.
   - Mention the relevant section/article/provision when supported.
   - Use bullets when they make the explanation clearer.
   - Do not add a "First, understand the basic idea" section unless it is
     genuinely useful.
   - Do not add hypothetical examples unless they materially improve
     understanding.
   - Avoid unrelated legal contexts.
   - Prefer a concise answer rather than an essay.
3. For a broad educational question:
   - Start with a short direct answer.
   - Explain the central legal concept in simple language.
   - Use clear headings and numbered points when useful.
   - Include examples, conditions, exceptions, and limitations when supported
     and useful for understanding.
   - For broad questions, a section such as "What this means in practice"
     may be used when it adds value.
4. Define unavoidable legal terms immediately in plain language. Do not
   assume the reader knows legal vocabulary.
5. Do not repeat information that was already established in the conversation
   unless repeating it is necessary to answer the new question.
6. Do not add filler, generic background, or unnecessary explanations simply
   to make the response longer.
7. When the retrieved evidence is insufficient, say so rather than filling
   the gap from general knowledge.
8. End with one brief sentence stating that the response provides general
   legal information and is not a substitute for advice from a qualified
   legal professional.
9. Format the answer as clean Markdown:
   - use ## headings for major sections when appropriate;
   - use ### headings only when genuinely needed;
   - use **bold** for important legal terms and conclusions;
   - use short paragraphs and properly indented bullet or numbered lists;
   - do not begin with a heading that says "Legal assistant";
   - do not create tables unless a comparison is genuinely clearer.
10. When answering in Malayalam, use clear, natural Malayalam wherever a
    familiar Malayalam expression exists. If an English legal term is useful,
    first explain it in Malayalam and then put the English term in
    parentheses.

CONVERSATION CONTEXT:
The following information may contain the previous user question and
assistant response. Use it only to understand the meaning of the current
follow-up. Do not treat previous assistant statements as legal evidence;
legal claims must still be supported by the retrieved passages.

ORIGINAL USER QUESTION:
{original_question}

{contextual_question_section}

CURRENT USER QUESTION:
{question}

ENGLISH RETRIEVAL QUERY:
{retrieval_question}

RETRIEVED LEGAL PASSAGES:
{context}

ANSWER IN {answer_language}:
"""

    pipeline_log("Gemini", "Generating grounded legal answer from retrieved passages")
    response = gemini_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    generated_answer = (response.text or "").strip()

    if not generated_answer:
        raise RuntimeError("Gemini returned an empty answer.")

    pipeline_log("RAG", "Grounded legal answer generated successfully")
    return {
        "original_question": original_question,
        "retrieval_query": retrieval_question,
        "answer_language": answer_language,
        "answer": generated_answer,
        "sources": retrieved
    }
def extract_document_text(file_path: str) -> str:
    """
    Extract text from a PDF while preserving PDF page numbers.
    """

    pipeline_log("Document analysis", "Extracting page-labelled text from uploaded PDF")
    pages = []

    with fitz.open(file_path) as document:
        for page_number, page in enumerate(
            document,
            start=1
        ):
            text = page.get_text("text").strip()

            if text:
                pages.append(
                    f"\n--- Page {page_number} ---\n{text}"
                )

    pipeline_log("Document analysis", f"Extracted text from {len(pages)} non-empty uploaded PDF page(s)")
    return "\n".join(pages)
def answer_uploaded_document_question(
    document_text: str,
    question: str,
    output_language: str = "auto"
):
    """
    Answer a question using only an uploaded document.
    """

    question = question.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    answer_language = determine_response_language(
        question=question,
        requested_language=output_language
    )

    prompt = f"""
You are an AI assistant explaining an uploaded legal document.

Answer the question using ONLY the uploaded document below.

Rules:
1. Answer in {answer_language}.
2. Do not use outside legal knowledge.
3. Do not invent clauses, dates, amounts, rights, or obligations.
4. Preserve all relevant exceptions, conditions, and limitations.
5. Cite supporting pages using labels such as [Page 1].
6. If the document does not contain enough information, clearly say so.
7. When answering in Malayalam, write constitutional article references
   using "ആർട്ടിക്കിൾ", for example "ആർട്ടിക്കിൾ 17".
8. Keep page citations in English format, such as [Page 3].
9. Explain the answer in simple language.
10. State that the answer is general information and not professional
    legal advice.

USER QUESTION:
{question}

UPLOADED DOCUMENT:
{document_text}

ANSWER IN {answer_language}:
"""

    pipeline_log("Document analysis", f"Generating document-grounded answer in {answer_language}")
    response = gemini_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    generated_answer = (response.text or "").strip()

    if not generated_answer:
        raise RuntimeError(
            "Gemini returned an empty document answer."
        )

    pipeline_log("Document analysis", "Document-grounded answer generated successfully")
    return {
        "question": question,
        "answer_language": answer_language,
        "answer": generated_answer
    }

def analyze_document(
    text: str,
    question: str | None = None,
    output_language: str = "auto"
):
    """
    Handle both document summarization and document-based Q&A.

    Document only:
        Returns a structured summary.

    Document + question:
        Answers the question using only the uploaded document.
    """

    text = text.strip()
    question = (question or "").strip()

    if not text:
        raise ValueError("Document text cannot be empty.")

    response_language = determine_response_language(
        question=question,
        requested_language=output_language
    )

    max_retries = 3
    pipeline_log(
        "Document analysis",
        f"Starting {'document Q&A' if question else 'structured summary'} in {response_language}; extracted text length: {len(text)} characters",
    )

    # --------------------------------------------------------
    # MODE 1: DOCUMENT + QUESTION
    # --------------------------------------------------------

    if question:
        # Document Q&A asks Gemini to use only the uploaded text; no Pinecone retrieval occurs.
        prompt = f"""
You are an AI assistant explaining an uploaded legal document.

Answer the user's question using ONLY the uploaded document below.

Rules:
1. Answer in {response_language}.
2. Do not use outside legal knowledge.
3. Do not invent clauses, dates, amounts, rights, or obligations.
4. Preserve relevant conditions, exceptions, and limitations.
5. Cite supporting pages using labels such as [Page 1].
6. If the document does not contain enough information, clearly say so.
7. Explain the answer in simple language.
8. Keep page citations in English format, such as [Page 3].
9. When answering in Malayalam, use "ആർട്ടിക്കിൾ" for constitutional
   article references rather than "അനുച്ഛേദം".
10. The answer is general legal information and not professional
    legal advice.

USER QUESTION:
{question}

UPLOADED DOCUMENT:
{text}

ANSWER IN {response_language}:
"""

        for attempt in range(max_retries):
            try:
                pipeline_log("Gemini", f"Generating document Q&A response (attempt {attempt + 1}/{max_retries})")
                response = gemini_client().models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt
                )

                answer = (response.text or "").strip()

                if not answer:
                    raise RuntimeError(
                        "Gemini returned an empty document answer."
                    )

                pipeline_log("Document analysis", "Document Q&A completed successfully")
                return {
                    "mode": "document_question_answer",
                    "question": question,
                    "output_language": response_language,
                    "answer": answer
                }

            except Exception as error:
                error_text = str(error)

                is_temporary_error = (
                    "503" in error_text
                    or "UNAVAILABLE" in error_text
                )

                if not is_temporary_error:
                    raise

                if attempt == max_retries - 1:
                    raise

                wait_time = 2 ** attempt

                pipeline_log("Gemini", f"Temporarily unavailable; retrying document Q&A in {wait_time} second(s)")

                time.sleep(wait_time)

    # --------------------------------------------------------
    # MODE 2: DOCUMENT ONLY
    # --------------------------------------------------------

    # Document-only analysis requests structured JSON from Gemini; no Pinecone retrieval occurs.
    prompt = f"""
You are an AI assistant explaining an uploaded legal document.

Analyze and summarize the document using only the information contained
in the document.

Write all JSON values in {response_language}.
Keep all JSON key names exactly as specified below in English.

Return ONLY valid JSON.
Do not use Markdown.
Do not wrap the response in ```json or ```.

Use exactly this JSON schema:

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
1. Use only information contained in the uploaded document.
2. Do not add outside legal knowledge.
3. Do not invent parties, clauses, dates, amounts, rights, or obligations.
4. Preserve important conditions, exceptions, and limitations.
5. Include page references such as [Page 1] when possible.
6. Keep dates, currency values, section numbers, and article numbers
   exactly as stated.
7. When writing Malayalam, use "ആർട്ടിക്കിൾ" for constitutional
   article references rather than "അനുച്ഛേദം".
8. If information is unavailable, use a short equivalent of
   "Not specified" in {response_language}.
9. This is general legal information and not professional legal advice.

UPLOADED DOCUMENT:
{text}
"""

    for attempt in range(max_retries):
        try:
            pipeline_log("Gemini", f"Generating structured document summary (attempt {attempt + 1}/{max_retries})")
            response = gemini_client().models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            response_text = (response.text or "").strip()

            if not response_text:
                raise RuntimeError(
                    "Gemini returned an empty document summary."
                )

            summary = json.loads(response_text)

            pipeline_log("Document analysis", "Structured document summary completed successfully")
            return {
                "mode": "document_summary",
                "output_language": response_language,
                "summary": summary
            }

        except Exception as error:
            error_text = str(error)

            is_temporary_error = (
                "503" in error_text
                or "UNAVAILABLE" in error_text
            )

            if not is_temporary_error:
                raise

            if attempt == max_retries - 1:
                raise

            wait_time = 2 ** attempt

            pipeline_log("Gemini", f"Temporarily unavailable; retrying structured summary in {wait_time} second(s)")

            time.sleep(wait_time)

    raise RuntimeError(
        "Document analysis failed unexpectedly."
    )


if __name__ == "__main__":
    ingest()
