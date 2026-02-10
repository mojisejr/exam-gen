"""
Main FastAPI Application
Controller layer that orchestrates AI and Document services.
"""
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional
import httpx
from pydantic import BaseModel
from fastapi import Depends, FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.services.ai_engine import (
    get_client,
    upload_to_gemini,
    agent_analyst,
    agent_architect,
    calculate_batches,
    generate_batch,
    normalize_topic,
)
from server.services.doc_generator import generate_docx
from server.schemas import ExamItem, Worksheet

# Setup Paths
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_runtime_output_dir() -> Path:
    """Resolve output directory for local dev or serverless runtime."""
    if os.getenv("VERCEL"):
        return Path(tempfile.gettempdir()) / "exam-gen-output"
    return OUTPUT_DIR


async def download_blob(file_url: str) -> str:
    """Download a blob URL into a temporary PDF file and return its path."""
    if not file_url.startswith("http"):
        raise HTTPException(status_code=422, detail="Invalid file_url")

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(file_url)
        response.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as buffer:
        buffer.write(response.content)
        return buffer.name


class RenderDocxRequest(BaseModel):
    worksheet: Worksheet

# Initialize FastAPI App
app = FastAPI(
    title="Exam Gen API",
    description="AI-powered exam generation from PDF documents",
    version="1.0.0"
)

# CORS Middleware (Allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def read_root():
    """Return API status info (UI handled by Next.js)."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Exam Gen API is running."}


def reindex_exam_items(worksheet: Worksheet) -> Worksheet:
    """
    Reindex exam item IDs sequentially from 1..N.

    Args:
        worksheet: Worksheet to reindex.

    Returns:
        Worksheet with sequential item IDs.
    """
    reindexed_items: List[ExamItem] = []
    for index, item in enumerate(worksheet.items, start=1):
        reindexed_items.append(item.model_copy(update={"id": index}))

    return worksheet.model_copy(update={"items": reindexed_items})


def get_api_key_header(
    x_gemini_api_key: Optional[str] = Header(default=None, alias="X-Gemini-API-Key"),
) -> Optional[str]:
    return x_gemini_api_key


@app.post("/generate-exam")
async def generate_exam(
    file: Optional[UploadFile] = File(None, description="PDF file to generate exam from"),
    file_url: Optional[str] = Form(default=None, description="Blob URL to PDF file"),
    api_key: Optional[str] = Depends(get_api_key_header),
    instruction: str = Form(
        default="ขอข้อสอบแนววิเคราะห์",
        description="Instructions for exam generation (e.g., difficulty, topic focus, style)"
    ),
    question_count: int = Form(
        default=10,
        description="Number of questions to generate"
    ),
    language: str = Form(
        default="ไทย",
        description="Language for generated questions (ไทย or English)"
    ),
    exam_type: str = Form(
        default="auto",
        description="Preferred exam type (auto, multiple_choice, true_false, subjective)"
    )
):
    """
    Generate an exam from a PDF file based on user instructions.
    
    Args:
        file: Uploaded PDF file.
        instruction: User's instruction for the exam.
    
    Returns:
        JSON response with download URL and brief.
    """
    try:
        # 1. Resolve PDF source (UploadFile or Blob URL)
        if file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as buffer:
                shutil.copyfileobj(file.file, buffer)
                file_path = buffer.name
        elif file_url:
            file_path = await download_blob(file_url)
        else:
            raise HTTPException(status_code=422, detail="file or file_url is required")
        
        # 2. Validate inputs
        allowed_counts = {10, 20, 30, 50}
        if question_count not in allowed_counts:
            raise HTTPException(status_code=422, detail="Invalid question_count. Allowed: 10, 20, 30, 50")

        allowed_languages = {"ไทย", "English"}
        if language not in allowed_languages:
            raise HTTPException(status_code=422, detail="Invalid language. Allowed: ไทย, English")

        allowed_exam_types = {"auto", "multiple_choice", "true_false", "subjective"}
        if exam_type not in allowed_exam_types:
            raise HTTPException(
                status_code=422,
                detail="Invalid exam_type. Allowed: auto, multiple_choice, true_false, subjective"
            )

        # 3. Initialize AI Client
        client = get_client(api_key)
        
        # 3. Upload to Gemini
        gemini_file = upload_to_gemini(client, file_path)
        
        # 4. Agent 1: Analyze content
        brief = agent_analyst(client, gemini_file, instruction, question_count, language)
        
        # 5. Agent 2: Design exam
        worksheet = agent_architect(
            client, gemini_file, brief, instruction, question_count, language, exam_type
        )

        # 6. Reindex items and prepare metadata
        worksheet = reindex_exam_items(worksheet)
        total_generated = len(worksheet.items)
        batches_planned = len(calculate_batches(question_count, max_batch=10))
        warning: Optional[str] = None
        if total_generated < question_count:
            warning = (
                f"Generated {total_generated} of {question_count} questions. "
                "Partial success due to model output variability."
            )

        # 7. Generate DOCX
        output_filename = f"worksheet_{os.urandom(4).hex()}.docx"
        runtime_output_dir = get_runtime_output_dir()
        runtime_output_dir.mkdir(parents=True, exist_ok=True)
        output_path = runtime_output_dir / output_filename
        generate_docx(worksheet, str(output_path))

        return {
            "status": "success",
            "message": "Exam generated successfully",
            "filename": output_filename,
            "brief": brief,
            "download_url": f"/download/{output_filename}",
            "requested_count": question_count,
            "total_generated": total_generated,
            "batches_planned": batches_planned,
            "warning": warning
        }
    
    except HTTPException as e:
        raise e
    except ValueError as e:
        # API Key or configuration errors
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")
    except Exception as e:
        # Other unexpected errors
        print(f"Error during exam generation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    finally:
        if "file_path" in locals() and os.path.exists(file_path):
            os.remove(file_path)


@app.post("/api/analyze")
async def analyze_pdf(
    file: Optional[UploadFile] = File(None, description="PDF file to analyze"),
    file_url: Optional[str] = Form(default=None, description="Blob URL to PDF file"),
    api_key: Optional[str] = Depends(get_api_key_header),
    instruction: str = Form(
        default="ขอข้อสอบแนววิเคราะห์",
        description="Instructions for exam generation"
    ),
    question_count: int = Form(
        default=10,
        description="Number of questions to generate"
    ),
    language: str = Form(
        default="ไทย",
        description="Language for generated questions"
    ),
    exam_type: str = Form(
        default="auto",
        description="Preferred exam type (auto, multiple_choice, true_false, subjective)"
    ),
):
    """Analyze PDF and return a design brief for batch generation."""
    try:
        if file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as buffer:
                shutil.copyfileobj(file.file, buffer)
                file_path = buffer.name
        elif file_url:
            file_path = await download_blob(file_url)
        else:
            raise HTTPException(status_code=422, detail="file or file_url is required")

        client = get_client(api_key)
        gemini_file = upload_to_gemini(client, file_path)
        allowed_exam_types = {"auto", "multiple_choice", "true_false", "subjective"}
        if exam_type not in allowed_exam_types:
            raise HTTPException(
                status_code=422,
                detail="Invalid exam_type. Allowed: auto, multiple_choice, true_false, subjective"
            )

        brief = agent_analyst(client, gemini_file, instruction, question_count, language)

        return {"brief": brief}
    finally:
        if "file_path" in locals() and os.path.exists(file_path):
            os.remove(file_path)


@app.post("/api/generate-batch")
async def generate_batch_endpoint(
    file: Optional[UploadFile] = File(None, description="PDF file to generate exam from"),
    file_url: Optional[str] = Form(default=None, description="Blob URL to PDF file"),
    api_key: Optional[str] = Depends(get_api_key_header),
    design_brief: str = Form(..., description="Design brief from analyzer"),
    instruction: str = Form(
        default="ขอข้อสอบแนววิเคราะห์",
        description="Instructions for exam generation"
    ),
    question_count: int = Form(
        default=10,
        description="Number of questions to generate in this batch"
    ),
    language: str = Form(
        default="ไทย",
        description="Language for generated questions"
    ),
    batch_info: str = Form(
        default="Batch 1/1",
        description="Batch progress metadata"
    ),
    avoid_topics: str = Form(
        default="ไม่มี",
        description="Topics to avoid, comma-separated"
    ),
    exam_type: str = Form(
        default="auto",
        description="Preferred exam type (auto, multiple_choice, true_false, subjective)"
    ),
):
    """Generate a single batch of questions with avoid-topics control."""
    try:
        if file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as buffer:
                shutil.copyfileobj(file.file, buffer)
                file_path = buffer.name
        elif file_url:
            file_path = await download_blob(file_url)
        else:
            raise HTTPException(status_code=422, detail="file or file_url is required")

        client = get_client(api_key)
        gemini_file = upload_to_gemini(client, file_path)
        topics = [
            normalize_topic(topic)
            for topic in avoid_topics.split(",")
            if topic.strip()
        ]

        allowed_exam_types = {"auto", "multiple_choice", "true_false", "subjective"}
        if exam_type not in allowed_exam_types:
            raise HTTPException(
                status_code=422,
                detail="Invalid exam_type. Allowed: auto, multiple_choice, true_false, subjective"
            )

        worksheet = generate_batch(
            client=client,
            file_obj=gemini_file,
            design_brief=design_brief,
            instruction=instruction,
            question_count=question_count,
            language=language,
            batch_info=batch_info,
            avoid_topics=topics,
            exam_type=exam_type,
        )

        new_topics = [normalize_topic(item.question) for item in worksheet.items]

        return {"worksheet": worksheet, "new_topics": new_topics}
    finally:
        if "file_path" in locals() and os.path.exists(file_path):
            os.remove(file_path)


@app.post("/api/render-docx")
async def render_docx(request: RenderDocxRequest):
    """Render DOCX from a worksheet payload and return the file."""
    output_filename = f"worksheet_{os.urandom(4).hex()}.docx"
    runtime_output_dir = get_runtime_output_dir()
    runtime_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = runtime_output_dir / output_filename

    # Ensure items are indexed correctly 1..N before rendering
    worksheet = reindex_exam_items(request.worksheet)
    generate_docx(worksheet, str(output_path))

    return FileResponse(
        str(output_path),
        filename=output_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Download a generated exam file.
    
    Args:
        filename: Name of the file to download.
    
    Returns:
        File response with the .docx file.
    """
    file_path = get_runtime_output_dir() / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        str(file_path),
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Exam Gen API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
