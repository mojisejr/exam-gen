"""
Configuration Module for Exam Gen
Centralizes environment variables, API settings, and prompt templates.
"""
import os
from dotenv import load_dotenv

# --- API Configuration ---
MODEL_NAME = "gemini-2.0-flash"

def get_api_key() -> str:
    """
    Validates and returns the Gemini API Key.
    
    Raises:
        ValueError: If GEMINI_API_KEY is not found in environment.
    """
    # Load environment variables fresh (for testing and reload scenarios)
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found. "
            "Please create a .env file with your API key."
        )
    return api_key

# --- Prompt Templates ---
PROMPT_TEMPLATES = {
    "analyst": """คุณคือผู้เชี่ยวชาญด้านหลักสูตรการสอน (Instructional Designer)
หน้าที่ของคุณคืออ่านเอกสาร PDF นี้แล้ววิเคราะห์เนื้อหาเพื่อเตรียมออกข้อสอบ

ข้อกำหนด: จำนวนข้อ {question_count} ข้อ, ภาษา {language}
โจทย์จากผู้ใช้: {instruction}

สิ่งที่คุณต้องสรุปส่งต่อให้คนออกข้อสอบ:
1. หัวข้อหลักของเนื้อหา (Key Topics)
2. ระดับความยากที่เหมาะสม (Level)
3. แนวทางการตั้งคำถามที่สอดคล้องกับ Bloom's Taxonomy
4. จุดสำคัญที่ควรเน้น (Focus Points)

ตอบเป็นภาษา {language} อย่างกระชับ""",
    
    "architect": """คุณคือผู้ออกข้อสอบระดับมืออาชีพ (Exam Architect)

ข้อกำหนด: จำนวนข้อ {question_count} ข้อ, ภาษา {language}
Instruction จากผู้ใช้: "{instruction}"

บริบทของงานย่อย: {batch_info}
หัวข้อที่ต้องหลีกเลี่ยง: {avoid_topics}

นี่คือข้อมูล Brief จากผู้วิเคราะห์หลักสูตร:
{design_brief}

หน้าที่ของคุณ:
สร้างแบบทดสอบตามโครงสร้าง JSON ที่กำหนด (Strict Schema) โดยยึด Instruction ของผู้ใช้เป็นหลัก (โดยเฉพาะจำนวนข้อและสไตล์)

ข้อกำหนด:
1. ออกข้อสอบตามจำนวน {question_count} ข้อเท่านั้น
2. ถ้าข้อไหนที่เหมาะกับการมีรูปประกอบ ให้ใส่ description ใน `image_prompt` (เป็นภาษาอังกฤษสำหรับ gen รูป เช่น "Diagram of...") ถ้าไม่มีให้ใส่ null
3. เนื้อหาต้องถูกต้องตาม PDF
4. ภาษาที่ใช้ในข้อสอบ ต้องเป็น {language} เท่านั้น
5. ทุกข้อมีฟิลด์ `type` ระบุรูปแบบคำถาม: `multiple_choice` | `true_false` | `subjective`
6. กติกาตามประเภท:
    - `multiple_choice`: ต้องมี `options` 4 ตัวเลือก (ก, ข, ค, ง) และ `correct_answer` เป็นหนึ่งใน ก/ข/ค/ง
    - `true_false`: ต้องมี `options` 2 ตัวเลือก (ถูก, ผิด) และ `correct_answer` เป็นหนึ่งใน ถูก/ผิด
    - `subjective`: `options` ต้องเป็น null และ `correct_answer` เป็นคำตอบแบบสั้นที่คาดหวัง
7. โครงสร้าง JSON ต้อง Strict และครบทุกฟิลด์ตาม Schema

Output เป็น JSON ตาม Schema เท่านั้น"""
}

def get_prompt(agent_type: str, **kwargs) -> str:
    """
    Retrieves a formatted prompt template for a specific agent.
    
    Args:
        agent_type: Type of agent ("analyst" or "architect").
        **kwargs: Variables to format into the template.
    
    Returns:
        Formatted prompt string.
    
    Raises:
        KeyError: If agent_type is not found in templates.
    """
    if agent_type not in PROMPT_TEMPLATES:
        raise KeyError(f"Prompt template '{agent_type}' not found.")
    
    return PROMPT_TEMPLATES[agent_type].format(**kwargs)
