"""
Test Core Configuration & Prompts
Tests the Brain: Config loading and prompt templating.
"""
import pytest
import os
from unittest.mock import patch
from server.config import get_api_key, get_prompt, MODEL_NAME
from server.main import reindex_exam_items
from server.schemas import Worksheet, ExamItem, Option


def test_model_name_configured():
    """Verify the model name is set correctly."""
    assert MODEL_NAME == "gemini-2.0-flash"


def test_prompt_integrity_analyst():
    """Test that instruction is embedded correctly in analyst prompt."""
    instruction = "ขอ 10 ข้อ แนววิเคราะห์"
    prompt = get_prompt("analyst", instruction=instruction, question_count=10, language="ไทย")
    
    assert instruction in prompt
    assert "Instructional Designer" in prompt
    assert "Key Topics" in prompt


def test_prompt_integrity_architect():
    """Test that instruction is embedded correctly in architect prompt."""
    instruction = "ขอ 20 ข้อ แนวท่องจำ"
    design_brief = "Mock brief content"
    batch_info = "Batch 1/2 (size 10)"
    avoid_topics = "หัวข้อ A, หัวข้อ B"
    exam_type_inst = "ต้องออกข้อสอบแบบ multiple_choice เท่านั้น"
    prompt = get_prompt(
        "architect",
        instruction=instruction,
        design_brief=design_brief,
        question_count=20,
        language="English",
        batch_info=batch_info,
        avoid_topics=avoid_topics,
        exam_type_instruction=exam_type_inst
    )
    
    assert instruction in prompt
    assert design_brief in prompt
    assert batch_info in prompt
    assert avoid_topics in prompt
    assert exam_type_inst in prompt
    assert "Exam Architect" in prompt


def test_prompt_invalid_type():
    """Test that invalid agent type raises KeyError."""
    with pytest.raises(KeyError):
        get_prompt("invalid_agent_type")


def test_api_key_guard_missing():
    """Test that missing API key raises ValueError."""
    import importlib
    import server.config
    
    # Clear environment AND patch load_dotenv to prevent .env file loading
    with patch.dict(os.environ, {}, clear=True):
        with patch("dotenv.load_dotenv"):
            # Reload the module to force re-evaluation under new environment
            importlib.reload(server.config)
            
            # Now test should raise ValueError
            with pytest.raises(ValueError, match="GEMINI_API_KEY not found"):
                server.config.get_api_key()


def test_api_key_success():
    """Test that valid API key is returned when set."""
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key_123"}):
        # Reload config to pick up new env
        import importlib
        import server.config
        importlib.reload(server.config)

        key = server.config.get_api_key()
        assert key == "test_key_123"


def test_calculate_batches_exact():
    """Test batch calculation for exact division."""
    from server.services.ai_engine import calculate_batches
    assert calculate_batches(50, 10) == [10, 10, 10, 10, 10]


def test_calculate_batches_remainder():
    """Test batch calculation when total is not divisible by max_batch."""
    from server.services.ai_engine import calculate_batches
    assert calculate_batches(25, 10) == [10, 10, 5]


def test_calculate_batches_invalid_total():
    """Test batch calculation invalid total_count."""
    from server.services.ai_engine import calculate_batches
    with pytest.raises(ValueError):
        calculate_batches(0, 10)


def test_calculate_batches_invalid_max_batch():
    """Test batch calculation invalid max_batch."""
    from server.services.ai_engine import calculate_batches
    with pytest.raises(ValueError):
        calculate_batches(10, 0)


def test_reindex_exam_items_sequential():
    """Test reindexing sets sequential IDs starting from 1."""
    worksheet = Worksheet(
        title="Mock",
        subject="Test",
        target_level="Any",
        items=[
            ExamItem(
                id=10,
                question="Q1",
                options=[Option(label="a", text="A")],
                correct_answer="a"
            ),
            ExamItem(
                id=5,
                question="Q2",
                options=[Option(label="a", text="A")],
                correct_answer="a"
            )
        ]
    )

    reindexed = reindex_exam_items(worksheet)
    assert [item.id for item in reindexed.items] == [1, 2]
