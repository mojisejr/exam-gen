"""
AI Engine Service
Handles all interactions with Google Gemini API for content analysis and exam generation.
"""
import os
from typing import List, Optional, Set
from google import genai
from google.genai import types

from app.config import get_api_key, get_prompt, MODEL_NAME
from app.schemas import Worksheet


def build_exam_type_instruction(exam_type: str) -> str:
    """
    Build a strict instruction string for exam type selection.

    Args:
        exam_type: Exam type preference (auto | multiple_choice | true_false | subjective).

    Returns:
        Thai instruction string to guide the architect prompt.
    """
    normalized = exam_type.strip().lower()
    if normalized in {"", "auto"}:
        return "ให้เลือกรูปแบบข้อสอบที่เหมาะสมจากเนื้อหา (สามารถผสมได้)"
    if normalized == "multiple_choice":
        return "ต้องออกข้อสอบแบบ multiple_choice เท่านั้น"
    if normalized == "true_false":
        return "ต้องออกข้อสอบแบบ true_false เท่านั้น"
    if normalized == "subjective":
        return "ต้องออกข้อสอบแบบ subjective เท่านั้น"
    return "ให้เลือกรูปแบบข้อสอบที่เหมาะสมจากเนื้อหา (สามารถผสมได้)"


def calculate_batches(total_count: int, max_batch: int = 10) -> List[int]:
    """
    Splits total_count into batch sizes capped by max_batch.

    Args:
        total_count: Total number of questions requested.
        max_batch: Maximum number of questions per batch.

    Returns:
        A list of batch sizes (e.g., 50 -> [10, 10, 10, 10, 10]).

    Raises:
        ValueError: If total_count or max_batch is not positive.
    """
    if total_count <= 0:
        raise ValueError("total_count must be positive")
    if max_batch <= 0:
        raise ValueError("max_batch must be positive")

    batches: List[int] = []
    remaining = total_count
    while remaining > 0:
        batch_size = min(max_batch, remaining)
        batches.append(batch_size)
        remaining -= batch_size
    return batches


def normalize_topic(text: str) -> str:
    """Normalize text for deduplication across batches."""
    return " ".join(text.strip().lower().split())


def get_client(api_key: Optional[str] = None) -> genai.Client:
    """
    Creates and returns a configured Gemini API client.
    
    Returns:
        genai.Client: Authenticated Gemini client.
    
    Raises:
        ValueError: If API key is not configured.
    """
    resolved_key = api_key.strip() if api_key else ""
    if not resolved_key:
        resolved_key = get_api_key()
    return genai.Client(api_key=resolved_key)


def upload_to_gemini(client: genai.Client, path: str, mime_type: str = "application/pdf"):
    """
    Uploads a file to Gemini for processing.
    
    Args:
        client: Authenticated Gemini client.
        path: Absolute path to the file to upload.
        mime_type: MIME type of the file (default: application/pdf).
    
    Returns:
        Uploaded file object from Gemini.
    
    Raises:
        Exception: If upload fails.
    """
    try:
        file_size = os.path.getsize(path)
        print(f"Uploading file: {path} ({file_size / 1024 / 1024:.2f} MB)")
        
        file = client.files.upload(file=path)
        print(f"Uploaded file '{file.name}' as: {file.uri}")
        print(f"State: {file.state.name}")
        return file
    except Exception as e:
        print(f"Upload failed: {e}")
        raise e


def agent_analyst(
    client: genai.Client,
    file_obj,
    instruction: str,
    question_count: int,
    language: str
) -> str:
    """
    Agent 1: Analyzes PDF content and creates a design brief for exam generation.
    
    Args:
        client: Authenticated Gemini client.
        file_obj: Uploaded file object from Gemini.
        instruction: User's instruction for the exam (e.g., difficulty, quantity).
    
    Returns:
        Design brief as a string (in Thai).
    
    Raises:
        Exception: If content generation fails.
    """
    print("\n[Agent 1] Analyst is analyzing content...")
    
    prompt = get_prompt(
        "analyst",
        instruction=instruction,
        question_count=question_count,
        language=language
    )
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[file_obj, prompt]
        )
        return response.text
    except Exception as e:
        print(f"[Agent 1] Error: {e}")
        raise e


def agent_architect(
    client: genai.Client,
    file_obj,
    design_brief: str,
    instruction: str,
    question_count: int,
    language: str,
    exam_type: str
) -> Worksheet:
    """
    Agent 2: Designs the exam worksheet based on the design brief.
    
    Args:
        client: Authenticated Gemini client.
        file_obj: Uploaded file object from Gemini.
        design_brief: Design brief from agent_analyst.
        instruction: Original user instruction.
    
    Returns:
        Worksheet object with structured exam questions.
    
    Raises:
        Exception: If exam generation fails.
    """
    print("\n[Agent 2] Architect is designing questions...")

    batch_sizes = calculate_batches(question_count, max_batch=10)
    total_batches = len(batch_sizes)
    aggregated_items = []
    existing_topics: Set[str] = set()
    worksheet_meta: Worksheet | None = None

    for index, batch_size in enumerate(batch_sizes, start=1):
        batch_info = f"Batch {index}/{total_batches} (size {batch_size})"
        avoid_topics = ", ".join(sorted(existing_topics)) if existing_topics else "ไม่มี"

        prompt = get_prompt(
            "architect",
            instruction=instruction,
            design_brief=design_brief,
            question_count=batch_size,
            language=language,
            batch_info=batch_info,
            avoid_topics=avoid_topics,
            exam_type_instruction=build_exam_type_instruction(exam_type)
        )

        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[file_obj, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Worksheet,
                )
            )
        except Exception as e:
            print(f"[Agent 2] Error: {e}")
            raise e

        parsed = response.parsed
        if parsed is None:
            raise ValueError("[Agent 2] Empty response from Gemini")

        if worksheet_meta is None:
            worksheet_meta = parsed

        for item in parsed.items:
            normalized = normalize_topic(item.question)
            if normalized in existing_topics:
                continue
            existing_topics.add(normalized)
            aggregated_items.append(item)

    if worksheet_meta is None:
        raise ValueError("[Agent 2] Failed to generate any batches")

    return Worksheet(
        title=worksheet_meta.title,
        subject=worksheet_meta.subject,
        target_level=worksheet_meta.target_level,
        items=aggregated_items
    )


def generate_batch(
    client: genai.Client,
    file_obj,
    design_brief: str,
    instruction: str,
    question_count: int,
    language: str,
    batch_info: str,
    avoid_topics: list[str],
    exam_type: str,
) -> Worksheet:
    """
    Generates a single batch of questions with avoid-topics control.

    Args:
        client: Authenticated Gemini client.
        file_obj: Uploaded file object from Gemini.
        design_brief: Design brief from agent_analyst.
        instruction: User instruction.
        question_count: Number of questions for this batch.
        language: Output language.
        batch_info: Batch indicator string.
        avoid_topics: List of normalized topics to avoid.

    Returns:
        Worksheet with batch items.
    """
    avoid_text = ", ".join(sorted(avoid_topics)) if avoid_topics else "ไม่มี"

    prompt = get_prompt(
        "architect",
        instruction=instruction,
        design_brief=design_brief,
        question_count=question_count,
        language=language,
        batch_info=batch_info,
        avoid_topics=avoid_text,
        exam_type_instruction=build_exam_type_instruction(exam_type),
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[file_obj, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Worksheet,
        ),
    )

    parsed = response.parsed
    if parsed is None:
        raise ValueError("[Batch] Empty response from Gemini")

    return parsed
