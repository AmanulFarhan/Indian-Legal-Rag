import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")

from src import rag


class SourceCitationTests(unittest.TestCase):
    def test_contract_act_section_heading_is_displayed(self):
        item = {
            "source": "contract.pdf",
            "document": "Indian Contract Act, 1872",
            "page": 14,
            "text": "14. \u201cFree consent\u201d defined.\u2014Consent is said to be free when it is not caused by coercion.",
        }
        self.assertEqual(rag.provision_from_passage(**{key: item[key] for key in ("text", "source", "document")}), "Section 14")
        self.assertEqual(rag.format_source_citation(item), "Indian Contract Act, 1872 — Section 14")

    def test_contract_act_second_section_heading_is_displayed(self):
        item = {
            "source": "contract.pdf",
            "text": "16. \u201cUndue influence\u201d defined.\u2014A contract is said to be induced by undue influence.",
        }
        self.assertEqual(rag.format_source_citation(item), "Indian Contract Act, 1872 — Section 16")

    def test_bns_section_heading_is_displayed(self):
        item = {"source": "bns.pdf", "text": "63. Rape.\u2014A man is said to commit rape if he does any of the following acts."}
        self.assertEqual(rag.format_source_citation(item), "Bharatiya Nyaya Sanhita, 2023 — Section 63")

    def test_constitution_heading_is_displayed_as_article(self):
        item = {"source": "constitution.pdf", "text": "21. Protection of life and personal liberty.\u2014No person shall be deprived of his life or personal liberty."}
        self.assertEqual(rag.format_source_citation(item), "Constitution of India, 1950 — Article 21")

    def test_unmapped_passage_has_no_page_or_invented_provision(self):
        item = {"source": "contract.pdf", "page": 14, "text": "Consent must be free for an agreement to become a contract."}
        citation = rag.format_source_citation(item)
        self.assertEqual(citation, "Indian Contract Act, 1872")
        self.assertNotIn("Page", citation)

    def test_retrieval_enriches_sources_without_changing_match_order(self):
        response = {"matches": [{"score": 0.9, "metadata": {"source": "contract.pdf", "document": "Indian Contract Act, 1872", "page": 14, "text": "14. \u201cFree consent\u201d defined.\u2014Consent is free."}}]}
        with patch.object(rag, "embedder") as embedder, patch.object(rag, "pinecone_index") as index:
            embedder.return_value.encode.return_value = [
                SimpleNamespace(tolist=lambda: [0.1, 0.2])
            ]
            index.return_value.query.return_value = response
            hits = rag.retrieve("What is free consent?", top_k=1)
        self.assertEqual(hits[0]["citation"], "Indian Contract Act, 1872 — Section 14")
        self.assertEqual(hits[0]["page"], 14)


if __name__ == "__main__":
    unittest.main()
