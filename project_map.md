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
- api/ : FastAPI backend และ AI orchestration (บรรจุ `index.py`, `requirements.txt`, `runtime.txt`)
- src/ : Next.js App Router (Dashboard + Batch UX) ย้ายมาที่ Root เพื่อความคล่องตัว (Flattened Layout)
- public/ : Static assets สำหรับ frontend
- tests/ : Pytest suite สำหรับ backend และ Vitest สำหรับ frontend
- data/ : Input staging (ignored)
- output/ : Generated artifacts (ignored)
- vercel.json : Runtime config แบบ Explicit Builds สำหรับ Vercel

## Data Flow
Frontend (Client-side Fetch) -> Vercel Rewrites (`/api/*`) -> api/index.py -> Gemini (AI Engine) -> Structured JSON -> DocX Generator -> Downloadable Artifact

## Deployment Strategy (Vercel Hardening)
- **Runtime Consistency**: ล็อค Node.js 22.x และ Python 3.11 เพื่อป้องกัน Environment Drift
- **Explicit Builds**: ใช้ `builds` ใน `vercel.json` แทนการพึ่งพา Auto-detect เพื่อความแม่นยำ 100%
- **BYOK (Security)**: ไม่เก็บ API Key บน Server (Vercel Env) แต่ใช้ Header Passing จาก Client-side เท่านั้น

## Challenges
- **Serverless Timeout**: การจัดการ Gemini Generation ที่ใช้เวลานาน (แก้ด้วย maxDuration 300s)
- **Vercel Payload Limit (413)**: ข้อจำกัด Request Body 4.5MB ของ Vercel (ต้องใช้ Vercel Blob สำหรับไฟล์ขนาดใหญ่)
- **Discovery Errors**: ป้องกัน shadowing error ด้วยการแยก `api/server` ออกจาก root `app` ของ Next.js
- **Environment "Baking"**: ระวังการตั้งค่า `NEXT_PUBLIC_` ที่อาจฝังค่า local ลงใน JavaScript ตอน build ตัวจริงบน Production
