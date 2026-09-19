from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
import tempfile, os

from .rag import answer, extract_document_text, analyze_document

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


@app.post("/analyze-document")
async def analyze_uploaded_document(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are currently supported."
        )

    contents = await file.read()

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    ) as temp:
        temp.write(contents)
        temp_path = temp.name

    try:
        text = extract_document_text(temp_path)

        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from the PDF."
            )

        analysis = analyze_document(text)

        return {
            "filename": file.filename,
            "analysis": analysis
        }

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)