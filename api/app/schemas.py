"""
Data Schemas for Exam Gen
Pydantic models for type-safe data validation across the application.
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """Supported question types for exam generation."""
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SUBJECTIVE = "subjective"


class Option(BaseModel):
    """Represents a single answer option in a multiple-choice question."""
    label: str = Field(..., description="Option label (a, b, c, d)")
    text: str = Field(..., description="The answer text")


class ExamItem(BaseModel):
    """Represents a single exam question with its metadata."""
    id: int = Field(..., description="Question number")
    question: str = Field(..., description="The question text")
    type: QuestionType = Field(
        QuestionType.MULTIPLE_CHOICE,
        description="Question format type"
    )
    options: Optional[List[Option]] = Field(
        None,
        description="List of answer choices (required for multiple_choice/true_false)"
    )
    correct_answer: str = Field(
        ..., 
        description="Correct answer label or text depending on question type"
    )
    explanation: Optional[str] = Field(None, description="Explanation of the answer")
    image_prompt: Optional[str] = Field(
        None, 
        description="English prompt for image generation (e.g., 'Diagram of...')"
    )


class Worksheet(BaseModel):
    """Represents a complete exam worksheet with all questions."""
    title: str = Field(..., description="Worksheet title")
    subject: str = Field(..., description="Subject name")
    target_level: str = Field(..., description="Target education level")
    items: List[ExamItem] = Field(..., description="List of exam questions")
