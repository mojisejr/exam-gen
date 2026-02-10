"""
Gate 2: Technical Flow (The Pipeline)
Validates API endpoints and file handling for exam-gen.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient
from dotenv import load_dotenv

from server.main import app, get_runtime_output_dir

DEFAULT_PDF_PATH = "/Users/non/dev/opilot/ψ/lab/exam-gen/data/test1.pdf"
DEFAULT_ORIGIN = "http://localhost:3000"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required env: {name}")
    return value


def require_file(path: str) -> Path:
    file_path = Path(path)
    if not file_path.exists():
        raise SystemExit(f"PDF not found: {file_path}")
    return file_path


def parse_filename(content_disposition: str) -> str:
    match = re.search(r"filename=([^;]+)", content_disposition)
    if not match:
        raise SystemExit("Could not parse filename from content-disposition")
    return match.group(1).strip().strip('"')


def assert_json_response(response, label: str) -> Dict[str, Any]:
    if response.status_code != 200:
        raise SystemExit(f"{label} failed: {response.status_code} {response.text}")
    if "application/json" not in response.headers.get("content-type", ""):
        raise SystemExit(f"{label} did not return JSON")
    return response.json()


def main() -> None:
    load_dotenv()
    require_env("GEMINI_API_KEY")

    pdf_path = require_file(os.getenv("EXAM_GEN_PDF_PATH", DEFAULT_PDF_PATH))
    origin = os.getenv("EXAM_GEN_ORIGIN", DEFAULT_ORIGIN)

    client = TestClient(app)

    # Connectivity Check: /health
    health_response = client.get("/health", headers={"Origin": origin})
    health_body = assert_json_response(health_response, "/health")
    if health_body.get("status") != "healthy":
        raise SystemExit("/health did not report healthy")

    # CORS Validation
    cors_response = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    cors_origin = cors_response.headers.get("access-control-allow-origin")
    if cors_origin not in ("*", origin):
        raise SystemExit(f"CORS header mismatch: {cors_origin}")

    # Flow Validation: /api/analyze
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
    analyze_body = assert_json_response(analyze_response, "/api/analyze")
    design_brief = analyze_body.get("brief")
    if not design_brief:
        raise SystemExit("/api/analyze missing brief")

    # Flow Validation: /api/generate-batch
    with pdf_path.open("rb") as handle:
        batch_response = client.post(
            "/api/generate-batch",
            files={"file": (pdf_path.name, handle, "application/pdf")},
            data={
                "design_brief": design_brief,
                "instruction": "ขอ 10 ข้อ แนววิเคราะห์",
                "question_count": "10",
                "language": "ไทย",
                "batch_info": "Batch 1/1",
                "avoid_topics": "ไม่มี",
            },
        )
    batch_body = assert_json_response(batch_response, "/api/generate-batch")
    worksheet = batch_body.get("worksheet")
    if not worksheet:
        raise SystemExit("/api/generate-batch missing worksheet")

    # Render DOCX (simulate serverless temp output)
    os.environ["VERCEL"] = "1"
    render_response = client.post(
        "/api/render-docx",
        json={"worksheet": worksheet},
    )
    if render_response.status_code != 200:
        raise SystemExit(f"/api/render-docx failed: {render_response.status_code}")
    if (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        not in render_response.headers.get("content-type", "")
    ):
        raise SystemExit("/api/render-docx did not return DOCX")

    output_dir = get_runtime_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    content_disposition = render_response.headers.get("content-disposition", "")
    filename = parse_filename(content_disposition)
    output_path = output_dir / filename

    if not output_path.exists():
        raise SystemExit(f"DOCX file not found on disk: {output_path}")

    # Clean up created file to keep /tmp tidy
    output_path.unlink(missing_ok=True)

    report = {
        "health": "ok",
        "cors": "ok",
        "analyze": "ok",
        "generate_batch": "ok",
        "render_docx": "ok",
        "output_dir": str(output_dir),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
