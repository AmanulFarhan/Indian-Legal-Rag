import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")

from src import rag


class IncrementalIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.raw_directory = Path(self.temp_directory.name) / "raw"
        self.raw_directory.mkdir()
        self.registry_path = Path(self.temp_directory.name) / "ingestion_registry.json"
        self.index = MagicMock()

    def tearDown(self):
        self.temp_directory.cleanup()

    def add_pdf(self, name, contents):
        path = self.raw_directory / name
        path.write_bytes(contents)
        return path

    def run_ingest(self):
        chunk = {"id": "chunk-id", "text": "14. Free consent.—Text.", "source": "document.pdf", "document": "Document", "page": 1, "chunk": 0}
        with patch.object(rag, "build_document_chunks", return_value=[chunk]) as build, \
             patch.object(rag, "generate_embeddings", return_value=[[0.1, 0.2]]), \
             patch.object(rag, "pinecone_index", return_value=self.index) as pinecone:
            rag.ingest(self.raw_directory, self.registry_path)
        return build, pinecone

    def test_first_ingestion_processes_new_pdf(self):
        self.add_pdf("document.pdf", b"first version")
        build, _ = self.run_ingest()
        self.assertEqual(build.call_count, 1)
        self.index.upsert.assert_called_once()
        self.assertEqual(len(rag.load_ingestion_registry(self.registry_path)["documents"]), 1)

    def test_same_pdf_is_skipped_on_a_later_run(self):
        self.add_pdf("document.pdf", b"same bytes")
        self.run_ingest()
        self.index.reset_mock()
        build, pinecone = self.run_ingest()
        build.assert_not_called()
        self.index.upsert.assert_not_called()
        pinecone.assert_not_called()

    def test_renamed_pdf_with_same_bytes_is_skipped(self):
        original = self.add_pdf("original.pdf", b"same bytes")
        self.run_ingest()
        original.unlink()
        self.add_pdf("renamed.pdf", b"same bytes")
        self.index.reset_mock()
        build, _ = self.run_ingest()
        build.assert_not_called()
        self.index.upsert.assert_not_called()

    def test_modified_pdf_is_processed_as_a_new_version(self):
        self.add_pdf("document.pdf", b"version one")
        self.run_ingest()
        self.add_pdf("document.pdf", b"version two")
        self.index.reset_mock()
        build, _ = self.run_ingest()
        self.assertEqual(build.call_count, 1)
        self.index.upsert.assert_called_once()
        self.assertEqual(len(rag.load_ingestion_registry(self.registry_path)["documents"]), 2)

    def test_failed_ingestion_is_not_registered_and_can_be_retried(self):
        self.add_pdf("document.pdf", b"retry me")
        with patch.object(rag, "build_document_chunks", return_value=[{"id": "chunk", "text": "text", "source": "document.pdf", "document": "Document", "page": 1, "chunk": 0}]), \
             patch.object(rag, "generate_embeddings", return_value=[[0.1]]), \
             patch.object(rag, "pinecone_index", return_value=self.index):
            self.index.upsert.side_effect = RuntimeError("Pinecone unavailable")
            with self.assertRaisesRegex(RuntimeError, "Ingestion failed"):
                rag.ingest(self.raw_directory, self.registry_path)
        self.assertEqual(rag.load_ingestion_registry(self.registry_path)["documents"], {})

        self.index.reset_mock(side_effect=True)
        self.run_ingest()
        self.assertEqual(len(rag.load_ingestion_registry(self.registry_path)["documents"]), 1)

    def test_existing_registered_documents_are_not_reprocessed_or_index_reset(self):
        self.add_pdf("document.pdf", b"existing")
        self.run_ingest()
        self.index.reset_mock()
        build, pinecone = self.run_ingest()
        build.assert_not_called()
        pinecone.assert_not_called()
        self.index.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
