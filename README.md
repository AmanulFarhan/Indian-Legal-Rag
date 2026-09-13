# Indian Legal RAG — Gemini Implementation

A research prototype for answering questions about Indian law using Retrieval-Augmented Generation (RAG):

Legal documents → cleaning and chunking → embeddings → Pinecone retrieval → context construction → Gemini → answer with sources.

This repository focuses on the core RAG pipeline, with an interactive terminal interface and a FastAPI backend.

## Current workflow

In our current setup, legal PDFs were downloaded manually, processed locally, and converted into embeddings. These embeddings, together with document text and source metadata, are already stored in Pinecone.

When a user asks a question, the application retrieves relevant passages from the existing Pinecone index and uses Gemini to generate an answer.

There is no need to download the PDFs again or repeat ingestion before normal querying. An automatic PDF download script is not required for this workflow.

The implementation uses:

- **SentenceTransformer** for document and query embeddings.
- **Pinecone** for vector storage and retrieval.
- **Gemini** for answer generation.
- **FastAPI** for the HTTP API.
- **PyMuPDF** for PDF text extraction during ingestion.

## Corpus

The selected corpus sources include primary Indian legal documents:

- Bharatiya Nyaya Sanhita, 2023
- Bharatiya Nagarik Suraksha Sanhita, 2023
- Bharatiya Sakshya Adhiniyam, 2023
- Consumer Protection Act, 2019
- Indian Contract Act, 1872
- Right to Information Act, 2005
- Constitution of India — optional

See `data/SOURCES.md` for source references.

The documents available for answering questions depend on what has actually been ingested into the configured Pinecone index.

## 1. Setup

Run commands from the repository root.

If you already have a Conda environment, activate it and use that environment. Otherwise, create a Python virtual environment:

```bash
python -m venv .venv
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

Or in Windows Command Prompt:

```bat
.venv\Scripts\activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Python-version compatibility with all pinned dependencies has not yet been verified.

## 2. Configure Gemini and Pinecone

Create a `.env` file in the repository root:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX=your_existing_index_name
EMBEDDING_MODEL=the_sentence_transformer_model_used_for_ingestion
TOP_K=5
```

Replace the placeholder values with your actual configuration.

### Gemini configuration

- `GEMINI_API_KEY`: your Gemini API key. The current code requires this variable when the module loads.
- `GEMINI_MODEL`: the model used for answer generation.

The current answer-generation code uses `gemini-2.5-flash` as its fallback. Confirm that the configured model is available to your account.

Gemini generates answers from retrieved passages. Embeddings are generated separately using SentenceTransformer.

### Pinecone configuration

- `PINECONE_API_KEY`: a key with access to your Pinecone index.
- `PINECONE_INDEX`: the name of your existing populated index.
- `EMBEDDING_MODEL`: the SentenceTransformer model used to generate the stored document embeddings.
- `TOP_K`: the default number of passages retrieved.

Use the same embedding model for ingestion and querying. Matching vector dimensions alone is not enough if the models differ.

For example, use:

```dotenv
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

only if that model was used for the existing document embeddings. This model produces 384-dimensional vectors.

Set `EMBEDDING_MODEL` explicitly. The current code's fallback embedding identifier is inconsistent with its SentenceTransformer implementation.

### Existing environment template

The tracked `.env.example` still contains older provider settings. If you copy it, replace those settings with the Gemini variables shown above.

Updating this README does not automatically update `.env.example`.

Keep `.env` and API keys out of version control.

## 3. Pinecone index and document preparation

### Using the existing index

Our legal PDFs have already been processed and stored in Pinecone.

For normal querying:

1. Configure access to the existing index.
2. Set the same embedding model used during ingestion.
3. Run the terminal interface or API.

You do not need to create a new index, download PDFs again, or repeat ingestion.

The index must contain the vectors and associated text/source metadata expected by the retrieval code.

### Creating a fresh index

For a new setup, create a Pinecone index compatible with your embedding model:

- **Name:** set this through `PINECONE_INDEX`.
- **Dimension:** match the embedding model's output dimension.
- **Metric:** cosine.
- **Cloud/region:** choose a supported configuration.

A 384-dimensional index is appropriate for `sentence-transformers/all-MiniLM-L6-v2`; other models may require different dimensions.

### Preparing new documents

When preparing a fresh corpus or adding documents:

1. Download the PDFs manually using the references in `data/SOURCES.md`.
2. Place them in `data/raw/`.
3. Configure the target Pinecone index and embedding model.
4. Run ingestion as described below.

No automatic corpus download script is required.

## 4. Ingest — only when needed

Skip this section when querying the existing populated index.

To process local PDFs:

```bash
python src/ingest.py
```

The ingestion pipeline:

1. Extracts PDF text with PyMuPDF.
2. Normalizes whitespace.
3. Splits text into overlapping chunks.
4. Generates SentenceTransformer embeddings.
5. Upserts vectors and metadata to Pinecone.

If you change the embedding model, regenerate document embeddings in a compatible index. Do not mix incompatible embedding models in the same retrieval workflow.

## 5. Query

### Interactive terminal

Run:

```bash
python src/query.py
```

Enter your question when prompted, for example:

```text
What is the right to information under Indian law?
```

The current script accepts questions through an interactive prompt. It does not read a question supplied as a command-line argument.

The output includes:

- The generated answer.
- Retrieved source filenames.
- Page numbers.
- Retrieval scores.

### FastAPI backend

Start the API:

```bash
uvicorn src.app:app --reload
```

Send a POST request to `/ask`:

```json
{
  "question": "What is a contract?",
  "top_k": 5
}
```

Example:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is a contract?","top_k":5}'
```

The API request's `top_k` field defaults to 5 when omitted.

The root GET endpoint `/` returns a basic API-running message. The question-answering endpoint is `/ask`.

## 6. Evaluation

Run:

```bash
python src/evaluate.py
```

The current evaluation uses a small set of retrieval questions and reports retrieval latency.

It does not establish answer correctness or legal accuracy. Expand the test set and compare generated answers against source documents before reporting performance results.

Results for this implementation must be measured independently; the referenced paper's accuracy figures are not results for this repository.

## Methodology

### Query pipeline

```text
User question
→ SentenceTransformer query embedding
→ Semantic retrieval from Pinecone
→ Context construction from retrieved passages
→ Gemini answer generation
→ Answer and sources
```

### Ingestion pipeline

```text
Local legal PDFs
→ Text extraction and cleaning
→ Overlapping chunks
→ SentenceTransformer embeddings
→ Pinecone vectors and metadata
```

## Project structure

```text
README.md          Project overview and usage
requirements.txt   Python dependencies
.env.example       Environment template requiring Gemini updates
data/SOURCES.md    Legal document source references
src/rag.py         Core ingestion, retrieval, and generation logic
src/ingest.py      Ingestion entry point
src/query.py       Interactive terminal interface
src/app.py         FastAPI backend
src/evaluate.py    Small retrieval evaluation
```

## Relationship to the referenced paper

The original README describes this project as a reproduction of the core RAG pipeline from *AI-Based Legal Assistant for Indian Legal Awareness* (2026).

According to that README, the paper uses Pinecone for vector storage and Groq-based models for generation. This implementation uses **Gemini** for answer generation.

The project retains the central workflow of semantic retrieval followed by context-based generation.

## Deviations from the paper

- This implementation uses Gemini as its answer-generation provider.
- The original README notes that the paper does not provide a complete reproducible configuration covering corpus, embedding model, chunk size, prompt, and retrieval settings. Record the configuration used when evaluating this implementation.
- The React/Tailwind UI, voice/TTS, multilingual interaction, Supabase authentication, and document-summary modules described in the original README remain optional extensions. They are not verified features of this backend.
- Evaluation uses a small retrieval test set. It does not reproduce or establish the paper's reported 85–88% accuracy.

## Current limitations

- The embedding model must match the model used for the existing Pinecone vectors.
- The index dimension must match the embedding model's output.
- The tracked `.env.example` still needs Gemini configuration updates.
- The code's fallback embedding identifier is inconsistent with the SentenceTransformer implementation; configure a compatible model explicitly.
- Dependency installation and Python-version compatibility have not been verified as part of this documentation update.
- The repository contains a backend and terminal interface; no frontend is currently tracked.
- Retrieved sources do not guarantee that an answer is correct or complete.

## Safety / legal disclaimer

This is a research and evaluation prototype, not a substitute for professional legal advice.

Check generated answers against the original source documents and current applicable law.

The application returns source filenames and page numbers to support verification. These should not be treated as verified Act or section citations without checking the underlying document.