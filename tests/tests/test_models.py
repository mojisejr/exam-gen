"""
Test Pydantic Schemas
Tests the Spine: Data validation and parsing.
"""
import pytest
from pydantic import ValidationError
from server.schemas import QuestionType, Option, ExamItem, Worksheet


def test_option_valid():
    """Test creating a valid Option."""
    option = Option(label="a", text="Answer A")
    assert option.label == "a"
    assert option.text == "Answer A"


def test_option_missing_field():
    """Test that missing required field raises ValidationError."""
    with pytest.raises(ValidationError):
        Option(label="a")  # Missing 'text'


def test_exam_item_valid():
    """Test creating a valid ExamItem."""
    item = ExamItem(
        id=1,
        question="Test question?",
        options=[
            Option(label="a", text="Answer A"),
            Option(label="b", text="Answer B"),
        ],
        correct_answer="a"
    )
    assert item.id == 1
    assert len(item.options) == 2
    assert item.explanation is None  # Optional field


def test_exam_item_optional_fields():
    """Test that optional fields default to None."""
    item = ExamItem(
        id=1,
        question="Test?",
        options=[Option(label="a", text="A")],
        correct_answer="a"
    )
    assert item.explanation is None
    assert item.image_prompt is None


def test_worksheet_valid():
    """Test creating a valid Worksheet."""
    worksheet = Worksheet(
        title="Test Exam",
        subject="Science",
        target_level="Grade 8",
        items=[
            ExamItem(
                id=1,
                question="Q1?",
                options=[Option(label="a", text="A")],
                correct_answer="a"
            )
        ]
    )
    assert worksheet.title == "Test Exam"
    assert len(worksheet.items) == 1


def test_worksheet_empty_items():
    """Test that Worksheet with empty items is valid."""
    worksheet = Worksheet(
        title="Empty Exam",
        subject="Test",
        target_level="Any",
        items=[]
    )
    assert len(worksheet.items) == 0


def test_question_type_enum():
    """Test QuestionType enum."""
    assert QuestionType.MULTIPLE_CHOICE.value == "multiple_choice"
