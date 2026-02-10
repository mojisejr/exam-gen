"""
Gate 3: Frontend Wiring (The Bridge)
Validates client-side orchestration flow against API endpoints.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from server.main import app, get_runtime_output_dir

DEFAULT_PDF_PATH = "/Users/non/dev/opilot/ψ/lab/exam-gen/data/test1.pdf"
DEFAULT_ORIGIN = "http://localhost:3000"


def build_batches(total: int, size: int) -> List[int]:
    batches: List[int] = []
    remaining = total
    while remaining > 0:
        batch = min(size, remaining)
        batches.append(batch)
        remaining -= batch
    return batches


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise AssertionError(f"Missing required env: {name}")
    return value


def require_file(path: str) -> Path:
    file_path = Path(path)
    if not file_path.exists():
        raise AssertionError(f"PDF not found: {file_path}")
    return file_path


def parse_filename(content_disposition: str) -> str:
    match = re.search(r"filename=([^;]+)", content_disposition)
    if not match:
        raise AssertionError("Could not parse filename from content-disposition")
    return match.group(1).strip().strip('"')


def test_frontend_wiring_gate3():
    load_dotenv()
    require_env("GEMINI_API_KEY")

    os.environ.setdefault("NEXT_PUBLIC_API_BASE_URL", DEFAULT_ORIGIN)
    os.environ["VERCEL"] = "1"

    pdf_path = require_file(os.getenv("EXAM_GEN_PDF_PATH", DEFAULT_PDF_PATH))

    client = TestClient(app)

    # Environment injection sanity check
    assert os.getenv("NEXT_PUBLIC_API_BASE_URL")

    # Analyze PDF
    with pdf_path.open("rb") as handle:
        analyze_response = client.post(
            "/api/analyze",
            files={"file": (pdf_path.name, handle, "application/pdf")},
            data={
                "instruction": "ขอ 10 ข้อ แนววิเคราะห์",
                "question_count": "10",
                "language": "ไทย",
            },
        )
    assert analyze_response.status_code == 200
    analyze_data = analyze_response.json()
    design_brief = analyze_data.get("brief")
    assert design_brief

    # Batch orchestration
    question_count = 10
    batches = build_batches(question_count, 10)
    collected_items = []
    avoid_topics: List[str] = []
    progress_log: List[int] = []
    worksheet_meta = None

    for index, batch_size in enumerate(batches, start=1):
        with pdf_path.open("rb") as handle:
            batch_response = client.post(
                "/api/generate-batch",
                files={"file": (pdf_path.name, handle, "application/pdf")},
                data={
                    "design_brief": design_brief,
                    "instruction": "ขอ 10 ข้อ แนววิเคราะห์",
                    "question_count": str(batch_size),
                    "language": "ไทย",
                    "batch_info": f"Batch {index}/{len(batches)}",
                    "avoid_topics": ", ".join(avoid_topics) or "ไม่มี",
                },
            )
        assert batch_response.status_code == 200
        batch_data = batch_response.json()

        worksheet = batch_data.get("worksheet")
        assert worksheet
        if worksheet_meta is None:
            worksheet_meta = {
                "title": worksheet["title"],
                "subject": worksheet["subject"],
                "target_level": worksheet["target_level"],
            }

        collected_items.extend(worksheet.get("items", []))
        avoid_topics.extend(batch_data.get("new_topics", []))

        progress_percent = round((index / len(batches)) * 100)
        progress_log.append(progress_percent)

        preview = json.dumps(worksheet.get("items", []), ensure_ascii=False, indent=2)
        assert preview

    assert worksheet_meta
    assert progress_log[-1] == 100
    assert all(progress_log[i] <= progress_log[i + 1] for i in range(len(progress_log) - 1))

    # Render DOCX
    render_response = client.post(
        "/api/render-docx",
        json={
            "worksheet": {
                **worksheet_meta,
                "items": collected_items,
            }
        },
    )
    assert render_response.status_code == 200
    assert (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        in render_response.headers.get("content-type", "")
    )

    content_disposition = render_response.headers.get("content-disposition", "")
    filename = parse_filename(content_disposition)

    output_dir = get_runtime_output_dir()
    output_path = output_dir / filename
    assert output_path.exists()

    # Cleanup temp artifact
    output_path.unlink(missing_ok=True)
