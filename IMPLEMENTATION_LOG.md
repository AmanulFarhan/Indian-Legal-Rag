# Implementation Log

## 2026-09-22 — Conversational follow-up questions

1. **What changed:** Added optional, session-only conversation history to knowledge-base questions and contextual query rewriting for follow-ups.
2. **Why:** Follow-up questions such as “What about it?” need the preceding legal concept to retrieve the correct passages.
3. **Files changed:** `src/app.py`, `src/rag.py`, `frontend/src/App.jsx`, `frontend/src/lib/api.js`, `tests/test_conversation.py`, and this log.
4. **How it works:** The frontend stores ordered `{ role: "user" | "assistant", content: string }` messages, sends the last 8 with `/ask`, and the backend asks Gemini to rewrite a follow-up as a standalone English retrieval question. Only that rewritten question is embedded and retrieved; the original question remains displayed.
5. **Testing:** Added mocked unit tests for a first question, no history, pronoun follow-up, prior legal concept, and multiple consecutive follow-ups.
6. **Limitations:** History is browser-session state only. The default is 8 messages (four turns) to preserve enough immediate context while bounding request size and model cost; `CONVERSATION_HISTORY_LIMIT` can be set from 2 to 20 on the backend. Contextualization depends on Gemini availability and may inherit ambiguity from an unclear conversation.

## 2026-09-22 — User-facing legal provision sources

1. **What changed:** Replaced page-number source display with document/year plus a text-supported Section or Article where available.
2. **Why:** PDF page numbers are not useful legal citations for users who do not have the same copy of the document.
3. **Files changed:** `src/rag.py`, `frontend/src/components/Sources.jsx`, `tests/test_sources.py`, and this log.
4. **How it works:** Existing Pinecone metadata already returns each chunk's legal text, source file, document, page, and chunk number. Retrieval now derives a provision only from an explicit Section/Article reference or a structured numbered provision heading in that returned text, then adds a display-only `citation` field. No vectors or Pinecone records are changed.
5. **Testing:** Added tests for Contract Act Sections 14 and 16, BNS Section 63, Constitution Article 21, an unmapped passage, and retrieval enrichment. Existing conversation tests remain part of the full test run.
6. **Limitations:** A passage without a confidently recognized provision heading falls back to document/year only. Page numbers remain in returned metadata for internal tracing and debugging but are intentionally not rendered in the Sources UI.

## 2026-09-22 — Incremental document ingestion

1. **What changed:** Added SHA-256 content-hash duplicate detection and a persistent successful-ingestion registry for incremental PDF ingestion.
2. **Why:** Re-running ingestion should add only new or changed PDFs, avoiding duplicate extraction, chunking, embeddings, and Pinecone upserts.
3. **Files changed:** `src/rag.py`, `.gitignore`, `tests/test_ingestion.py`, and this log.
4. **How it works:** Each PDF is hashed before processing. `data/ingestion_registry.json` stores hashes only after every batch for that document upserts successfully. Known hashes are skipped even if the filename changes; changed bytes produce a new hash and new hash-suffixed vector IDs. Existing Pinecone metadata remains `text`, `source`, `document`, `page`, and `chunk`.
5. **Testing:** Added focused tests for first ingestion, repeat skip, renamed-file skip, modified-file processing, failed-upsert retry, and ensuring registered documents do not cause index reset calls.
6. **Limitations:** The registry begins tracking documents from this change onward. Existing vectors have no stored content hash, so they cannot be safely registered automatically without a verified migration; they are left untouched. A failed multi-batch upload can leave partial vectors, but it is never marked complete and a retry re-upserts the same hash-based IDs.

## 2026-09-23 — Historical corpus registry bootstrap

1. **What changed:** Added a manual, one-time bootstrap utility for the seven historical PDFs: BNS, BNSS, BSA, Constitution, Contract Act, CPA, and RTI Act.
2. **Why:** Their 970 vectors predate SHA-256 registry tracking, so their hashes must be registered locally to prevent an incremental ingestion run from treating them as new documents.
3. **Files changed:** `scripts/bootstrap_ingestion_registry.py`, `tests/test_bootstrap_ingestion_registry.py`, and this log.
4. **How it works:** The utility verifies all seven expected PDFs before writing, calls the existing `pdf_content_hash()` function for each, previews every full hash, then merges hash-keyed entries with their known informational chunk counts into `data/ingestion_registry.json`. Existing entries are preserved; a same-source/different-hash conflict stops the migration.
5. **Testing:** Added tests for hash registration with preserved registry entries, missing-file no-write behavior, same-source/different-hash safety conflicts, idempotent second runs, and no Pinecone client calls.
6. **Limitations:** This is a one-time migration that records the currently available PDF bytes as the historical identities; the counts are informational and do not independently prove corpus equivalence. The script must be run manually and performs no PDF extraction, chunking, embeddings, Pinecone connection, upsert, reset, or metadata changes.

## 2026-09-23 — Pipeline terminal logging and corrected embedding comments

1. **What changed:** Added structured terminal logs for API requests, ingestion, hashing, registry decisions, local embeddings, Pinecone retrieval/upserts, translation, conversational rewriting, Gemini answer generation, and uploaded-document analysis; corrected stale embedding comments and the Sentence Transformer fallback model.
2. **Why:** The running backend should make its pipeline stages observable, and code comments must accurately state that Sentence Transformers—not Gemini—create vectors.
3. **Files changed:** `src/rag.py` and this log.
4. **How it works:** `pipeline_log()` prints concise `[Stage]` messages around operations without printing API keys, full uploaded documents, or full user questions. Comments now distinguish local Sentence Transformer embeddings from Gemini language/generation calls.
5. **Testing:** Existing mocked ingestion, retrieval, source, conversation, and bootstrap tests are run after the log changes.
6. **Limitations:** Logs show stage and count information rather than full prompt/document contents to avoid noisy output and accidental exposure of user-provided legal material.

## 2026-09-23 — Composer reset and visible first-answer sources

1. **What changed:** The prompt text and attached PDF now clear immediately after a valid send, and retrieved Sources panels render open by default.
2. **Why:** Users should be able to begin the next prompt while a request is processing, and the first RAG response should visibly show its returned legal sources without requiring an extra click.
3. **Files changed:** `frontend/src/App.jsx`, `frontend/src/components/Composer.jsx`, `frontend/src/components/Sources.jsx`, and this log.
4. **How it works:** The request captures the draft and file before state is reset, so the in-flight API call is unchanged. Resetting the hidden file input permits attaching the same PDF again. Sources still resolve `[S#]` labels to the returned retrieval results, but their native details panel starts expanded.
5. **Testing:** Frontend lint and production build are run after the UI-only change.
6. **Limitations:** Sources are only available for knowledge-base RAG answers; uploaded-document summary/Q&A responses do not return Pinecone sources.
