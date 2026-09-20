# Nyaya — Indian Legal RAG Assistant

Nyaya is a multilingual legal-information assistant that implements the core
Retrieval-Augmented Generation (RAG) approach from the assigned paper. It
retrieves relevant passages from an indexed Indian legal corpus and asks Gemini
to answer using that evidence. It also summarizes uploaded legal PDFs and
answers questions grounded only in an uploaded document.

The application provides general legal information and does not replace advice
from a qualified legal professional.

## Problem addressed

Indian legal documents are long, technical, and difficult for readers without
legal training. A general language model may provide fluent but unsupported
answers. This project reduces that risk by retrieving legal text before answer
generation and instructing the model to stay within the supplied evidence.

## Implemented features

- English and Malayalam legal questions.
- Malayalam-to-English query translation for English-corpus retrieval.
- Semantic search over multiple Indian legal documents in Pinecone.
- Beginner-friendly answers with document and PDF-page sources.
- PDF-only upload for structured legal-document summaries.
- PDF plus question for document-grounded question answering.
- Browser speech-to-text input in English or Malayalam.
- React, Vite, and Tailwind interface with configurable language, retrieval
  depth, and source visibility.

## Core architecture

```text
1. BUILD THE PERMANENT KNOWLEDGE BASE (one-time ingestion)

Official legal PDFs
        |
        v
Extract text page by page
        |
        v
Clean text and preserve document/page metadata
        |
        v
Create overlapping chunks
        |
        +--------------------------+
        |                          |
        v                          v
Generate MiniLM embeddings    Attach source metadata
        |                          |
        +------------+-------------+
                     v
            Pinecone vector index


2. ANSWER A KNOWLEDGE-BASE QUESTION

English or Malayalam question
        |
        v
Is the question Malayalam?
    | Yes                     | No
    v                         v
Translate to English      Use original query
    |                         |
    +------------+------------+
                 v
        Generate query embedding
                 |
                 v
Search Pinecone for similar legal chunks
                 |
                 v
Build context from retrieved passages
                 |
                 +-----------------------------+
                 |                             |
                 v                             v
       Original user question        Retrieved legal context
                 |                             |
                 +--------------+--------------+
                                v
                  Gemini grounded generation
                                |
                 +--------------+--------------+
                 |                             |
                 v                             v
        Plain-language answer       Document names and PDF pages


3. ANALYZE A NEWLY UPLOADED PDF

Uploaded PDF
      |
      v
Validate file and extract page-labelled text
      |
      v
Was a question included?
    | No                      | Yes
    v                         v
Create structured summary    Answer only from uploaded PDF
    |                         |
    +------------+------------+
                 v
      Conversational document result
```

The first workflow runs only when the legal corpus is ingested. Normal legal
questions use the second workflow and search the existing Pinecone index. The
third workflow analyzes a user-uploaded document for the current request and
does not add it to Pinecone.

## RAG methodology

### Ingestion

1. Discover PDFs under `data/raw/`.
2. Extract text page by page with PyMuPDF.
3. Normalize whitespace while preserving page metadata.
4. Split page text into overlapping chunks.
5. Generate normalized 384-dimensional embeddings with
   `sentence-transformers/all-MiniLM-L6-v2`.
6. Store vectors and source metadata in a cosine-similarity Pinecone index.

### Query answering

1. Validate the question and determine the requested answer language.
2. Translate Malayalam questions to English for retrieval; English questions
   are used unchanged.
3. Embed the retrieval query with the same MiniLM model used during ingestion.
4. Retrieve the configured number of passages from Pinecone.
5. Construct a prompt containing the original question and retrieved evidence.
6. Generate a plain-language answer with Gemini.
7. Display the relevant source documents and pages separately in the UI.

### Uploaded documents

The backend extracts page-labelled text from an uploaded PDF. Without a
question, Gemini returns a structured summary. With a question, Gemini answers
using only the uploaded document. Uploaded PDFs are not inserted into the
permanent Pinecone index.

## Legal corpus

| Repository file | Legal document |
|---|---|
| `bns.pdf` | Bharatiya Nyaya Sanhita, 2023 |
| `bnss.pdf` | Bharatiya Nagarik Suraksha Sanhita, 2023 |
| `bsa.pdf` | Bharatiya Sakshya Adhiniyam, 2023 |
| `cpa.pdf` | Consumer Protection Act, 2019 |
| `contract.pdf` | Indian Contract Act, 1872 |
| `rta.pdf` | Right to Information Act, 2005 source file |
| `constitution.pdf` | Constitution of India |

The effective query corpus depends on which records have been ingested into the
configured Pinecone index. Official source references are recorded in
[data/SOURCES.md](data/SOURCES.md).

## `src/rag.py` function reference

| Function | Responsibility |
|---|---|
| `embedder()` | Lazily loads and reuses the configured Sentence Transformer model so it is not loaded for every request. |
| `gemini_client()` | Lazily creates and reuses the Gemini client from the local environment configuration. |
| `contains_malayalam(text)` | Detects whether the input contains any character from the Malayalam Unicode block. |
| `determine_response_language(question, requested_language)` | Validates `auto`, `english`, or `malayalam`; explicit choices win, while `auto` follows the question language. |
| `translate_query_to_english(question)` | Returns English questions unchanged and asks Gemini to translate Malayalam legal queries without answering them. |
| `pinecone_index()` | Lazily connects to and reuses the configured Pinecone index. |
| `extract_pdf(path)` | Extracts non-empty PDF text page by page and preserves numeric page metadata for ingestion. |
| `clean_text(text)` | Normalizes whitespace, removes empty lines, and returns cleaner text for chunking. |
| `chunk_text(text, chunk_size, overlap)` | Splits text into overlapping word chunks and ignores a final fragment shorter than 40 words. |
| `document_name(filename)` | Maps known PDF filenames to readable legal-document titles and derives a title for unknown filenames. |
| `build_chunks()` | Runs extraction, cleaning, and chunking for every PDF in `data/raw/`, then adds vector IDs and source metadata. |
| `generate_embeddings(texts)` | Encodes all chunk texts in batches, normalizes the vectors, and converts them to lists for Pinecone. |
| `ingest()` | Orchestrates corpus preparation, embedding generation, and batched Pinecone upserts. |
| `retrieve(question, top_k)` | Embeds a query, performs Pinecone similarity search, and returns text, metadata, and numeric similarity scores. |
| `answer(question, top_k, output_language)` | Runs the complete RAG question-answering path: language handling, translation, retrieval, context construction, Gemini generation, and source return. |
| `extract_document_text(file_path)` | Extracts an uploaded PDF into one string with explicit page labels such as `--- Page 3 ---`. |
| `answer_uploaded_document_question(document_text, question, output_language)` | Standalone helper that answers a question using only supplied document text. The active API route uses `analyze_document()` for the combined workflow. |
| `analyze_document(text, question, output_language)` | Handles both upload modes: document-only structured summary and document-plus-question answering, including retries for temporary Gemini `503` errors. |

## Main interfaces

### Frontend

The React interface supports typed or dictated questions, PDF attachment,
response-language selection, retrieval-depth selection, source visibility, and
conversational rendering of answers and document summaries.

### FastAPI

- `GET /` serves the production frontend.
- `GET /api/health` checks backend availability without calling an AI service.
- `POST /ask` accepts a question, retrieval depth, and output language.
- `POST /analyze-document` accepts a PDF plus an optional question and output
  language.
- `GET /docs` exposes interactive API documentation while the server runs.

## Technology used

- **Backend:** Python 3.12, FastAPI, Uvicorn, PyMuPDF
- **Retrieval:** Sentence Transformers, Pinecone cosine search
- **Generation and translation:** Google Gemini
- **Frontend:** React 19, Vite 8, Tailwind CSS 4, React Markdown

## Evaluation and verification

`src/evaluate.py` contains representative retrieval questions for the RTI Act,
Indian Contract Act, BNS, BSA, and BNSS. It reports top-five document hits and
retrieval latency. The configured Pinecone index must be populated before this
evaluation is run.

Implementation verification completed during development:

- Python modules compile successfully.
- FastAPI serves the React production build and health route.
- PDF validation rejects unsupported or empty uploads.
- ESLint passes.
- The Vite production build completes successfully.
- Python dependency consistency passes with `pip check`.

Generated legal answers still require qualitative review for factual support,
correct document scope, preservation of exceptions, and page-level source
alignment.

## Deviations from the paper

- FastAPI is used instead of Flask.
- Gemini performs query translation, grounded generation, and uploaded-document
  analysis.
- Sentence Transformers and Pinecone implement retrieval.
- Uploaded documents are analyzed for the current request instead of being
  inserted into the permanent vector index.
- Internal retrieval labels are used to identify supporting passages but are
  removed from the displayed answer; users see document names and page numbers.
- Browser-native speech recognition provides voice input without an additional
  backend audio service.

## Limitations

- Retrieval quality depends on PDF extraction, chunk boundaries, and the
  records actually stored in Pinecone.
- Word-based chunks can rank an exact provision below related passages;
  section-aware chunking and reranking would improve retrieval.
- Image-only PDFs require OCR, which is not currently implemented.
- Malayalam retrieval depends on machine translation and may lose legal nuance.
- Speech-recognition availability and quality vary by browser and device.
- Broad questions may require legislation or case law outside the indexed
  corpus.
- Gemini may temporarily return provider-capacity errors such as `503`.

## Setup

See [SETUP.md](SETUP.md) for cross-platform installation, environment
configuration, and startup commands.
