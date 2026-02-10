"""
Test API Flow
Tests the Face: End-to-End Integration via FastAPI endpoints.
"""
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from server.main import app


client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint_serves_ui():
    """Test that root endpoint serves JSON info."""
    response = client.get("/")
    assert response.status_code == 200
    # Should return JSON content (API-only mode)
    assert "application/json" in response.headers.get("content-type", "")
    body = response.json()
    assert "message" in body


def test_generate_exam_endpoint(sample_pdf, mock_gemini_client, tmp_path):
    """Test the main exam generation endpoint with mocked AI."""
    # Mock at the destination (where main.py imports from)
    with patch("server.main.get_client", return_value=mock_gemini_client):
        with patch("server.main.upload_to_gemini") as mock_upload:
            # Mock file upload
            mock_file_obj = MagicMock()
            mock_file_obj.uri = "mock://uri"
            mock_upload.return_value = mock_file_obj
            
            # Mock AI agents to return deterministic results
            with patch("server.main.agent_analyst") as mock_analyst:
                with patch("server.main.agent_architect") as mock_architect:
                    # Mock analyst returns a design brief
                    mock_analyst.return_value = "Mock Design Brief: 5 questions, analytical style."
                    
                    # Mock architect returns a valid Worksheet (no real AI call)
                    from server.schemas import Worksheet, ExamItem, Option
                    mock_worksheet = Worksheet(
                        title="แบบทดสอบ",
                        subject="วิชาทดสอบ",
                        target_level="ระดับมัธยมศึกษา",
                        items=[
                            ExamItem(
                                id=1,
                                question="ข้อใดคือคำตอบที่ถูกต้อง?",
                                options=[
                                    Option(label="ก", text="ตัวเลือก A"),
                                    Option(label="ข", text="ตัวเลือก B"),
                                ],
                                correct_answer="ก"
                            )
                        ]
                    )
                    mock_architect.return_value = mock_worksheet
                    
                    # Prepare test file
                    with open(sample_pdf, "rb") as f:
                        files = {"file": ("test.pdf", f, "application/pdf")}
                        data = {
                            "instruction": "ขอ 5 ข้อ แนววิเคราะห์",
                            "question_count": "10",
                            "language": "ไทย"
                        }
                        
                        response = client.post("/generate-exam", files=files, data=data)
    
    # Assertions
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "success"
    assert "download_url" in json_data
    assert "filename" in json_data
    assert json_data["requested_count"] == 10
    assert json_data["total_generated"] == 1
    assert json_data["batches_planned"] == 1
    assert json_data["warning"] is not None


def test_download_file_not_found():
    """Test downloading a non-existent file returns 404."""
    response = client.get("/download/nonexistent.docx")
    assert response.status_code == 404


def test_generate_exam_invalid_question_count(sample_pdf):
    """Test invalid question_count returns 422 before AI calls."""
    with open(sample_pdf, "rb") as f:
        files = {"file": ("test.pdf", f, "application/pdf")}
        data = {
            "instruction": "ขอ 5 ข้อ แนววิเคราะห์",
            "question_count": "999",
            "language": "ไทย"
        }

        response = client.post("/generate-exam", files=files, data=data)

    assert response.status_code == 422


def test_generate_exam_invalid_language(sample_pdf):
    """Test invalid language returns 422 before AI calls."""
    with open(sample_pdf, "rb") as f:
        files = {"file": ("test.pdf", f, "application/pdf")}
        data = {
            "instruction": "ขอ 5 ข้อ แนววิเคราะห์",
            "question_count": "10",
            "language": "JP"
        }

        response = client.post("/generate-exam", files=files, data=data)

    assert response.status_code == 422
