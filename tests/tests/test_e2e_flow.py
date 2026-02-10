"""
E2E Flow Test
Exercises the full HTTP pipeline with mocked AI responses.
"""
import os
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from docx import Document

from server.main import app, OUTPUT_DIR
from server.schemas import Worksheet, ExamItem, Option


client = TestClient(app)


def _build_mock_worksheet(total_items: int) -> Worksheet:
    items = []
    for index in range(1, total_items + 1):
        items.append(
            ExamItem(
                id=100 + index,
                question=f"Question {index}",
                options=[
                    Option(label="a", text="Option A"),
                    Option(label="b", text="Option B"),
                    Option(label="c", text="Option C"),
                    Option(label="d", text="Option D"),
                ],
                correct_answer="a"
            )
        )

    return Worksheet(
        title="E2E Exam",
        subject="E2E Subject",
        target_level="E2E Level",
        items=items
    )


def test_generate_exam_e2e_batch_50(sample_pdf):
    """E2E-style test: request 50 questions and validate response + DOCX output."""
    mock_client = MagicMock()

    with patch("server.main.get_client", return_value=mock_client):
        with patch("server.main.upload_to_gemini") as mock_upload:
            mock_file_obj = MagicMock()
            mock_file_obj.uri = "mock://uri"
            mock_upload.return_value = mock_file_obj

            with patch("server.main.agent_analyst") as mock_analyst:
                with patch("server.main.agent_architect") as mock_architect:
                    mock_analyst.return_value = "Mock Design Brief"
                    mock_architect.return_value = _build_mock_worksheet(50)

                    with open(sample_pdf, "rb") as f:
                        files = {"file": ("test.pdf", f, "application/pdf")}
                        data = {
                            "instruction": "ขอ 50 ข้อ แนววิเคราะห์",
                            "question_count": "50",
                            "language": "ไทย"
                        }

                        response = client.post("/generate-exam", files=files, data=data)

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_count"] == 50
    assert payload["total_generated"] == 50
    assert payload["batches_planned"] == 5
    assert payload["warning"] is None

    output_filename = payload["filename"]
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    assert os.path.exists(output_path)

    doc = Document(output_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    assert "1. Question 1" in text
    assert "50. Question 50" in text

    os.remove(output_path)