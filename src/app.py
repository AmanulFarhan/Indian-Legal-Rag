import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .rag import answer, extract_document_text, analyze_document

app = FastAPI(
    title="Indian Legal AI Assistant",
    description="RAG-based legal awareness assistant for Indian law",
    version="1.0.0"
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)


class QuestionRequest(BaseModel):
    question: str
    top_k: int = 5
    output_language: str = "auto"



@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/ask")
def ask_question(request: QuestionRequest):
    try:
        return answer(
            question=request.question,
            top_k=request.top_k,
            output_language=request.output_language
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


@app.post("/analyze-document")
async def analyze_uploaded_document(
    file: UploadFile = File(...),
    question: str | None = Form(None),
    output_language: str = Form("auto")
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are currently supported."
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The uploaded PDF is empty."
        )

    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="The PDF must be smaller than 50 MB."
        )

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

        analysis = analyze_document(
            text=text,
            question=question,
            output_language=output_language
        )

        return {
            "filename": file.filename,
            "analysis": analysis
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        ) from error

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
