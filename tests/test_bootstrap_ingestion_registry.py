import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")

from scripts.bootstrap_ingestion_registry import (
    HISTORICAL_DOCUMENTS,
    bootstrap_historical_registry,
)
from src import rag


class HistoricalRegistryBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.raw_directory = Path(self.temporary_directory.name) / "raw"
        self.raw_directory.mkdir()
        self.registry_path = Path(self.temporary_directory.name) / "ingestion_registry.json"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def add_historical_pdfs(self):
        for filename in HISTORICAL_DOCUMENTS:
            (self.raw_directory / filename).write_bytes(f"fixture:{filename}".encode())

    def test_bootstrap_registers_hashes_and_preserves_existing_entries(self):
        self.add_historical_pdfs()
        existing_hash = "existing-hash"
        rag.save_ingestion_registry({
            "version": 1,
            "documents": {existing_hash: {"source": "unrelated.pdf", "chunk_count": 1}},
        }, self.registry_path)

        with patch.object(rag, "pinecone_index") as pinecone_index:
            registry = bootstrap_historical_registry(self.raw_directory, self.registry_path)

        self.assertIn(existing_hash, registry["documents"])
        self.assertEqual(len(registry["documents"]), len(HISTORICAL_DOCUMENTS) + 1)
        for filename, chunk_count in HISTORICAL_DOCUMENTS.items():
            content_hash = rag.pdf_content_hash(self.raw_directory / filename)
            self.assertEqual(registry["documents"][content_hash]["source"], filename)
            self.assertEqual(registry["documents"][content_hash]["chunk_count"], chunk_count)
            self.assertTrue(registry["documents"][content_hash]["historical_bootstrap"])
        pinecone_index.assert_not_called()

    def test_missing_pdf_fails_without_writing_a_partial_registry(self):
        self.add_historical_pdfs()
        (self.raw_directory / "rta.pdf").unlink()
        original_registry = {"version": 1, "documents": {"keep": {"source": "keep.pdf"}}}
        rag.save_ingestion_registry(original_registry, self.registry_path)
        original_contents = self.registry_path.read_text(encoding="utf-8")

        with self.assertRaisesRegex(FileNotFoundError, "rta.pdf"):
            bootstrap_historical_registry(self.raw_directory, self.registry_path)

        self.assertEqual(self.registry_path.read_text(encoding="utf-8"), original_contents)

    def test_running_bootstrap_twice_is_idempotent(self):
        self.add_historical_pdfs()
        first_registry = bootstrap_historical_registry(self.raw_directory, self.registry_path)
        first_contents = self.registry_path.read_text(encoding="utf-8")
        second_registry = bootstrap_historical_registry(self.raw_directory, self.registry_path)

        self.assertEqual(first_registry, second_registry)
        self.assertEqual(self.registry_path.read_text(encoding="utf-8"), first_contents)
        self.assertEqual(len(second_registry["documents"]), len(HISTORICAL_DOCUMENTS))

    def test_conflicting_source_hash_stops_without_writing(self):
        self.add_historical_pdfs()
        rag.save_ingestion_registry({
            "version": 1,
            "documents": {"different-hash": {"source": "contract.pdf", "chunk_count": 57}},
        }, self.registry_path)
        original_contents = self.registry_path.read_text(encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "different hash"):
            bootstrap_historical_registry(self.raw_directory, self.registry_path)

        self.assertEqual(self.registry_path.read_text(encoding="utf-8"), original_contents)


if __name__ == "__main__":
    unittest.main()
