# Indian Legal RAG — Paper Reproduction

A fast reproduction of the **core RAG pipeline** described in *AI-Based Legal Assistant for Indian Legal Awareness* (2026): legal documents → cleaning/chunking → embeddings → vector retrieval → context construction → Groq LLM → grounded answer.

The paper specifies Pinecone for vector storage and Groq-based language models for generation, and describes semantic retrieval followed by context-grounded generation. It also lists document analysis, voice, multilingual support and authentication as additional modules. This repository prioritizes the core RAG implementation for a one-day evaluation.

## Corpus
The initial corpus is intended to contain primary Indian legal sources from Government of India / India Code:
- Bharatiya Nyaya Sanhita, 2023
- Bharatiya Nagarik Suraksha Sanhita, 2023
- Bharatiya Sakshya Adhiniyam, 2023
- Consumer Protection Act, 2019
- Indian Contract Act, 1872
- Right to Information Act, 2005
- Constitution of India (optional due to size)

See `data/SOURCES.md` for authoritative source URLs. Run `python src/download_corpus.py` to download them.

## 1. Setup

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env  # Linux/macOS
```

Fill in `GROQ_API_KEY` and `PINECONE_API_KEY`.

## 2. Create Pinecone index

The index must use the same embedding dimension as the selected model. `all-MiniLM-L6-v2` produces 384-dimensional vectors.

Using the Pinecone console, create:
- Name: `indian-legal-rag`
- Dimension: `384`
- Metric: `cosine`
- Cloud/region: any supported serverless configuration

## 3. Collect corpus

```bash
python src/download_corpus.py
```

Only use the authoritative URLs listed in `data/SOURCES.md`. Keep source metadata with each document.

## 4. Ingest

```bash
python src/ingest.py
```

Pipeline:
1. Extract PDF text with PyMuPDF.
2. Normalize whitespace.
3. Chunk text with overlap.
4. Generate sentence-transformer embeddings.
5. Upsert chunks and metadata to Pinecone.

## 5. Query

```bash
python src/query.py "What is the right to information under Indian law?"
```

Or run the API:

```bash
uvicorn src.app:app --reload
```

Then POST `/query` with:

```json
{"question":"What is a contract?","top_k":5}
```

## 6. Evaluation

```bash
python src/evaluate.py
```

This provides a small reproducible qualitative retrieval test and reports retrieval latency. Add more questions before submission.

## Methodology

The implementation follows the paper's described workflow:

`User Query → Query Embedding → Semantic Retrieval → Context Creation → LLM Response`

For ingestion:

`Legal PDFs → Text Extraction/Cleaning → Chunking → Embedding → Pinecone`

## Safety / legal disclaimer
This is a research/evaluation prototype, not a substitute for professional legal advice. Answers are expected to be grounded in retrieved source text and should expose the source Act/section metadata used by the model.

## Deviations from the paper
- The paper does not specify a single public corpus, exact embedding model, chunk size, prompt, top-k, or complete reproducible configuration. This implementation makes those choices explicit.
- The paper's React/Tailwind UI, voice/TTS, multilingual interaction, Supabase authentication and document-summary module are not required for the core one-day reproduction and are treated as optional extensions.
- Evaluation is reproduced with a small transparent test set rather than claiming the paper's reported 85–88% accuracy. New results must be measured independently.
