# Project Map: exam-gen

## Philosophy
แพลตฟอร์มสร้างข้อสอบจากเอกสาร PDF ด้วย AI โดยเน้นความแม่นยำ ความเร็ว และประสบการณ์ใช้งานที่ลื่นไหล

## Key Landmarks
- api/ : FastAPI backend และ AI orchestration
- app/ : Next.js frontend (Dashboard + Batch UX)
- tests/ : Pytest suite สำหรับ backend
- data/ : Input staging (ignored)
- output/ : Generated artifacts (ignored)
- vercel.json : Runtime config สำหรับ Vercel

## Data Flow
Frontend (app/) -> API (api/index.py) -> Gemini -> JSON -> DOCX -> Response

## Challenges
- Serverless timeout และการจัดการไฟล์แบบ in-memory
- การคง schema กลางให้ตรงกันระหว่าง Python และ TypeScript
