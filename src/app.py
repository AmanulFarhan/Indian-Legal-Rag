from fastapi import FastAPI
from pydantic import BaseModel

from .rag import answer

app = FastAPI(
    title="Indian Legal AI Assistant",
    description="RAG-based legal awareness assistant for Indian law",
    version="1.0.0"
)


class QuestionRequest(BaseModel):
    question: str
    top_k: int = 5


@app.get("/")
def root():
    return {
        "message": "Indian Legal AI Assistant API is running"
    }


@app.post("/ask")
def ask_question(request: QuestionRequest):
    result = answer(
        request.question,
        request.top_k
    )

    return result