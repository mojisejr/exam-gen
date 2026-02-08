# Project Map: exam-gen

## Philosophy
แพลตฟอร์มสร้างข้อสอบอัจฉริยะจากเอกสาร PDF ที่รองรับรูปแบบคำถามที่หลากหลาย (Multiple Choice, True/False, Subjective) โดยเน้นความแม่นยำ ความเร็ว และประสบการณ์ใช้งานที่ลื่นไหล

## Repository
- GitHub: https://github.com/mojisejr/exam-gen

## Implementation Strategy (The Workflow)
เพื่อให้การพัฒนาเป็นระบบและรักษาความสะอาดของ Repository:
1. **Development Hub**: พัฒนาและรวมโค้ดใน branch `staging` (Local) เป็นหลัก
2. **Feature Isolation**: ทุกฟีเจอร์ใหม่จะถูกสร้างแยกเป็น `feature/*` โดย checkout ออกจาก `staging` เสมอ
3. **Merging & Deployment**:
   - เมื่อฟีเจอร์เสร็จ จะ merge กลับเข้า `staging`
   - Push `staging` ขึ้น remote เพื่อทำ CI/CD หรือเตรียม Deployment
   - จะไม่ยุ่งกับ branch `main` บน remote โดยตรงจนกว่าจะพร้อม Release

## Key Landmarks
- api/ : FastAPI backend และ AI orchestration
- app/ : Next.js frontend (Dashboard + Batch UX)
- tests/ : Pytest suite สำหรับ backend
- data/ : Input staging (ignored)
- output/ : Generated artifacts (ignored)
- vercel.json : Runtime config สำหรับ Vercel

## Data Flow
Frontend (app/) -> API (api/index.py) -> Gemini (Multi-format Prompting) -> Structured JSON -> Doc Rendering Helpers -> DOCX -> Response

## Challenges
- Serverless timeout และการจัดการไฟล์แบบ in-memory
- การคุมความถูกต้องของ JSON Schema เมื่อมีการใช้หลายประเภทข้อสอบพร้อมกัน (Hybrid Schema Validation)
- การจัดรูปแบบ (Formatting) ใน DOCX ให้สอดคล้องกับธรรมชาติของแต่ละรูปแบบข้อสอบ
- การคง schema กลางให้ตรงกันระหว่าง Python และ TypeScript
