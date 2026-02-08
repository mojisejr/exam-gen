"""
Pytest Configuration & Shared Fixtures
"""
import pytest
import os
from unittest.mock import MagicMock
from app.schemas import Worksheet, ExamItem, Option


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client to avoid real API calls."""
    client = MagicMock()
    
    # Mock file upload response
    mock_file = MagicMock()
    mock_file.uri = "gemini://mock-file-uri"
    mock_file.name = "test.pdf"
    mock_file.state.name = "ACTIVE"
    client.files.upload.return_value = mock_file
    
    # Mock analyst response (brief text)
    analyst_response = MagicMock()
    analyst_response.text = "Mock brief: 5 ข้อสอบวิเคราะห์ระดับมัธยม"
    
    # Mock architect response (structured worksheet)
    mock_worksheet = Worksheet(
        title="Mock Exam",
        subject="Mock Subject",
        target_level="มัธยม",
        items=[
            ExamItem(
                id=1,
                question="Question 1?",
                options=[
                    Option(label="a", text="Answer A"),
                    Option(label="b", text="Answer B"),
                    Option(label="c", text="Answer C"),
                    Option(label="d", text="Answer D"),
                ],
                correct_answer="a",
                explanation="Explanation for Q1"
            )
        ]
    )
    
    architect_response = MagicMock()
    architect_response.parsed = mock_worksheet
    
    # Configure client to return these responses
    client.models.generate_content.side_effect = [analyst_response, architect_response]
    
    return client


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a temporary dummy PDF file."""
    pdf_path = tmp_path / "test.pdf"
    # Create minimal PDF structure (not a real PDF, but sufficient for testing)
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")
    return str(pdf_path)


@pytest.fixture
def mock_worksheet():
    """Returns a valid Worksheet instance for testing."""
    return Worksheet(
        title="Test Worksheet",
        subject="Mathematics",
        target_level="Grade 10",
        items=[
            ExamItem(
                id=1,
                question="What is 2+2?",
                options=[
                    Option(label="a", text="3"),
                    Option(label="b", text="4"),
                    Option(label="c", text="5"),
                    Option(label="d", text="6"),
                ],
                correct_answer="b",
                explanation="2+2 equals 4"
            ),
            ExamItem(
                id=2,
                question="What is the capital of France?",
                options=[
                    Option(label="a", text="London"),
                    Option(label="b", text="Berlin"),
                    Option(label="c", text="Paris"),
                    Option(label="d", text="Madrid"),
                ],
                correct_answer="c"
            )
        ]
    )
