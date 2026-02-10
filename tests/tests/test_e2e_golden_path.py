"""
E2E Golden Path Test (Live).
Runs the full pipeline against real PDF + Gemini API.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from docx import Document

from server.main import app, OUTPUT_DIR


client = TestClient(app)


def _resolve_pdf_path() -> Path:
    env_path = os.getenv(
        "EXAM_GEN_E2E_PDF_PATH",
        "/Users/non/dev/opilot/ψ/lab/exam-gen/data/test1.pdf",
    )
    return Path(env_path).expanduser()


@pytest.mark.e2e
@pytest.mark.live
def test_e2e_golden_path_subjective_20_questions():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set; skipping live E2E test.")

    pdf_path = _resolve_pdf_path()
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_path}")

    with pdf_path.open("rb") as file_handle:
        files = {"file": (pdf_path.name, file_handle, "application/pdf")}
        data = {
            "instruction": "ขอ 20 ข้อ แนววิเคราะห์",
            "question_count": "20",
            "language": "ไทย",
            "exam_type": "subjective",
        }
        response = client.post("/generate-exam", files=files, data=data)

    assert response.status_code == 200
    payload = response.json()
    assert payload.get("requested_count") == 20
    assert payload.get("total_generated") == 20
    assert payload.get("batches_planned") == 2

    output_filename = payload.get("filename")
    assert output_filename
    output_path = Path(OUTPUT_DIR) / output_filename
    assert output_path.exists()

    doc = Document(str(output_path))
    text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    numbers = [int(match.group(1)) for match in re.finditer(r"\b(\d{1,3})\. ", text)]
    assert numbers
    assert numbers[0] == 1
    assert numbers[-1] == 20
    assert len(numbers) == 20

    output_path.unlink(missing_ok=True)
