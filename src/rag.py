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
        return question

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

    return translation

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

def answer(
    question: str,
    top_k: int = TOP_K,
    output_language: str = "auto"
):
    original_question = question.strip()

    if not original_question:
        raise ValueError("Question cannot be empty.")

    # Malayalam becomes English. English remains unchanged.
    retrieval_question = translate_query_to_english(
        original_question
    )

    answer_language = determine_response_language(
        question=original_question,
        requested_language=output_language
    )

    # Pinecone is searched using the English version.
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

    prompt = f"""
You are a careful Indian legal information assistant teaching a reader who
has no previous legal knowledge.

Answer using only the retrieved legal passages supplied below. Your goal is
to help the reader understand the law, not merely list provisions.

ACCURACY AND SCOPE RULES:
1. Answer in {answer_language}.
2. Do not treat related legal terms as identical. For example, "human
   rights" is broader than "Fundamental Rights". Explain the distinction
   when it matters and state which part the retrieved documents support.
3. Never imply that the retrieved documents are the whole of Indian law.
   For a broad question, clearly state the scope of the available evidence.
4. Use only the supplied passages for legal claims. Do not invent or add
   laws, sections, cases, penalties, procedures, remedies, or facts.
5. Preserve every important condition, exception, qualification, and
   limitation found in the passages.
6. Cite each substantive legal claim immediately with one or more supplied
   labels, such as [S1] or [S1, S3]. Do not cite a passage that does not
   support the claim.
   These labels identify retrieved source passages; they are not legal
   section or article numbers.
7. If evidence is missing or only partially answers the question, explain
   exactly what can be answered and what cannot be confirmed from the
   retrieved documents.
8. Keep citation labels unchanged when answering in Malayalam.

WRITING RULES FOR A BEGINNER:
1. Start with a short, direct answer of two or three sentences.
2. Add a section called "First, understand the basic idea" and explain the
   central legal term in everyday language.
3. Explain the important points under clear numbered headings. For each
   point, include when supported:
   - what it means in simple language;
   - a short everyday hypothetical example marked as an example; and
   - any legal limitation or exception in the passages.
4. Define unavoidable legal terms immediately in plain language. Prefer
   short sentences and common words. Do not assume the reader knows legal
   vocabulary.
5. For broad questions, finish with "What this means in practice" and give
   a concise practical understanding based only on the supplied evidence.
6. Use enough detail to teach the topic properly, but do not repeat the same
   information or add filler. A narrow question should remain focused; a
   broad question may require a longer structured explanation.
7. End with one brief sentence stating that the response provides general
   legal information and is not a substitute for advice from a qualified
   legal professional.
8. Format the answer as clean Markdown:
   - use ## headings for major sections;
   - use ### headings only when a subsection is genuinely needed;
   - use **bold** for important legal terms and conclusions;
   - use short paragraphs and properly indented bullet or numbered lists;
   - do not begin with a heading that says "Legal assistant";
   - do not create tables unless a comparison is genuinely clearer in one.
9. When answering in Malayalam, use clear, natural Malayalam wherever a
   familiar Malayalam expression exists. If an English legal term is useful,
   first explain it in Malayalam and then put the English term in parentheses.

ORIGINAL USER QUESTION:
{original_question}

ENGLISH RETRIEVAL QUERY:
{retrieval_question}

RETRIEVED LEGAL PASSAGES:
{context}

ANSWER IN {answer_language}:
"""

    response = gemini_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    generated_answer = (response.text or "").strip()

    if not generated_answer:
        raise RuntimeError("Gemini returned an empty answer.")

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

    response = gemini_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    generated_answer = (response.text or "").strip()

    if not generated_answer:
        raise RuntimeError(
            "Gemini returned an empty document answer."
        )

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

    # --------------------------------------------------------
    # MODE 1: DOCUMENT + QUESTION
    # --------------------------------------------------------

    if question:
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
                response = gemini_client().models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt
                )

                answer = (response.text or "").strip()

                if not answer:
                    raise RuntimeError(
                        "Gemini returned an empty document answer."
                    )

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

                print(
                    f"Gemini temporarily unavailable. "
                    f"Retrying in {wait_time} seconds..."
                )

                time.sleep(wait_time)

    # --------------------------------------------------------
    # MODE 2: DOCUMENT ONLY
    # --------------------------------------------------------

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

            print(
                f"Gemini temporarily unavailable. "
                f"Retrying in {wait_time} seconds..."
            )

            time.sleep(wait_time)

    raise RuntimeError(
        "Document analysis failed unexpectedly."
    )
