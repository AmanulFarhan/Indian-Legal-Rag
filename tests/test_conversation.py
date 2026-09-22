import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")

from src import rag


class FakeModels:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def generate_content(self, **kwargs):
        self.prompts.append(kwargs["contents"])
        return SimpleNamespace(text=next(self.responses))


class ConversationAnswerTests(unittest.TestCase):
    def answer_with(self, question, history, model_responses):
        models = FakeModels(model_responses)
        client = SimpleNamespace(models=models)
        retrieved = [{"document": "Indian Contract Act", "source": "contract.pdf", "page": 10, "score": 0.9, "text": "Legal passage."}]
        with patch.object(rag, "gemini_client", return_value=client), \
             patch.object(rag, "translate_query_to_english", side_effect=lambda value: value), \
             patch.object(rag, "retrieve", return_value=retrieved) as retrieve:
            result = rag.answer(question, conversation_history=history)
        return result, models.prompts, retrieve.call_args.args[0]

    def test_first_question_uses_existing_retrieval_path(self):
        result, prompts, retrieval_query = self.answer_with("What is free consent?", [], ["Answer"])
        self.assertEqual(result["original_question"], "What is free consent?")
        self.assertEqual(retrieval_query, "What is free consent?")
        self.assertEqual(len(prompts), 1)

    def test_pronoun_follow_up_is_contextualized(self):
        history = [{"role": "user", "content": "What is free consent under Indian Contract Law?"}, {"role": "assistant", "content": "Free consent is consent not caused by coercion, undue influence, fraud, misrepresentation, or mistake."}]
        _, prompts, retrieval_query = self.answer_with("How does it apply?", history, ["How does free consent apply under Indian Contract Law?", "Answer"])
        self.assertIn("How does it apply?", prompts[0])
        self.assertEqual(retrieval_query, "How does free consent apply under Indian Contract Law?")

    def test_previous_legal_concept_is_retained(self):
        history = [{"role": "user", "content": "What is free consent?"}, {"role": "assistant", "content": "It is consent freely given."}]
        _, _, retrieval_query = self.answer_with("What about undue influence?", history, ["What is undue influence in relation to free consent under Indian Contract Law?", "Answer"])
        self.assertIn("free consent", retrieval_query)

    def test_question_without_history_does_not_rewrite(self):
        _, prompts, retrieval_query = self.answer_with("What is coercion?", None, ["Answer"])
        self.assertEqual(retrieval_query, "What is coercion?")
        self.assertEqual(len(prompts), 1)

    def test_multiple_follow_ups_use_recent_ordered_history(self):
        history = [{"role": "user", "content": "What is free consent?"}, {"role": "assistant", "content": "It means consent freely given."}, {"role": "user", "content": "What is undue influence?"}, {"role": "assistant", "content": "It is a way consent may be improperly obtained."}]
        _, prompts, retrieval_query = self.answer_with("How is this different from coercion?", history, ["How is undue influence, as a factor affecting free consent, different from coercion under Indian Contract Law?", "Answer"])
        self.assertIn("What is free consent?", prompts[0])
        self.assertIn("What is undue influence?", prompts[0])
        self.assertIn("different from coercion", retrieval_query)


if __name__ == "__main__":
    unittest.main()
